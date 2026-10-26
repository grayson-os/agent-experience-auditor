# Architecture Canvas Diagram Specification

Draw the module topology on the OutSystems Architecture Canvas by writing a small JSON model and rendering it with `scripts/render_canvas.py`. The script lays the canvas out as three full-width layers stacked in a single column (End User, Core, Foundation), splits each layer into its sub-layers, draws every reference, and highlights violations.

The same model drives two outputs:

- **Interactive diagram** (`architecture-canvas.html`), from the template in [../assets/canvas-artifact.html](../assets/canvas-artifact.html). It is the primary diagram wherever you can publish an Artifact, such as Claude.
- **SVG diagram** (`architecture-canvas.svg`), for agents and viewers without Artifacts, and for the final report.

Both use the same layout and the same rules, so their violation numbers, cycles, and gaps match.

There is **no Orchestration layer**. Never use it, in the diagram or anywhere else in the audit.

## 1. Classify Each Module

Assign every module a `layer` and a `sublayer` from this table. Use the module name's suffix first. An `M` after the underscore marks a mobile module (for example `_MCW`, `_MBL`, `_MCS`, `_MPat`) and belongs in the same sub-layer as its non-mobile form.

| `layer` | `sublayer` | Suffixes | Holds |
| :--- | :--- | :--- | :--- |
| `end-user` | `End User` | `_UI`, `_MUI`, or no suffix | User-facing screens and flows. Entry or "orchestration" modules, often without a suffix, also belong here |
| `core` | `API` | `_API`, `_OAPI` | Wrappers that expose APIs to external consumers (`_API`) or service actions to other OutSystems domains (`_OAPI`) |
| `core` | `Core Widgets` | `_CW` | Reusable business blocks |
| `core` | `Composite Logic` | `_BL`, `_Eng`, `_Sync` | Isolated business logic, calculation engines, and synchronization with external systems |
| `core` | `Core Service` | `_CS` | Reusable core services with public entities and their actions |
| `foundation` | `Style Guide` | `_Pat`, `_Th` | UI patterns and themes, including `OutSystemsUI` |
| `foundation` | `Foundation Service` | `_IS`, `_Drv` | Integration services and drivers that wrap external systems |
| `foundation` | `Library` | `_Lib` | Generic libraries |
| `foundation` | `Plugin` | `_Plug` | Specific third-party features |

Integration Services (`_IS`) are **Foundation**, not Core.

When a suffix is missing or misleading, classify by what the module contains: screens go to End User, public entities with their CRUD actions go to Core Service, business-agnostic wrappers of external systems go to Foundation Service. Record each classification you made by content, and why, in the findings.

## 2. Choose What to Include

- **Modules**: the audited module, every module it references (producers), and every module that references it (consumers) that the MCP tools expose. Also include every module involved in a finding.
- **Leave out** the `System` module, since every module references it.
- **Large estates**: if there are more than 30 modules, keep the audited module, its direct producers and consumers, and every module involved in a finding. List the rest in `omitted`.
- **References**: one entry per module-to-module reference, from the consumer to the producer. Do not add one entry per element. Record the references **of every module in the diagram**, not just the audited one's. A cycle such as `Order_BL -> Order_CS -> Customer_CS -> Order_BL` only shows up when `Order_CS` and `Customer_CS` have their own references recorded.

### Checking each module's references

For each module in the diagram, use the MCP tools to read the modules it references, and record those references. Then set `"references_checked": true` on that module.

The Service Studio MCP reads the module open in Service Studio, so it may not show the references of other modules. When you can't read a module's references:

- Leave `references_checked` out for that module. The script then marks it with a **?** in the diagram and lists it under **Gaps**, because a cycle through it can't be ruled out.
- Add a **Verify in Environment** row: "Open `<Module>` in Service Studio and re-run the architecture audit, or check its dependencies in Discovery or the Architecture Dashboard."
- Don't report a cycle you can't see, and don't state there are no cycles. Say which modules weren't checked.

If `os11-audit/architecture-canvas.json` exists from an earlier run of this audit on the same application, load it and keep its `references_checked` modules. Replace a module's references with what you read now whenever you inspect that module again. This lets the user open each producer module in turn and build up a complete model.

### OutSystems and Forge modules

Mark modules supplied by OutSystems or installed from Forge (for example `Users`, `OutSystemsUI`, `RichWidgets`) with `"owner": "platform"` (baseline entry ARCH-PLATFORM-MODULES). The script draws them dashed and never flags their own references as upward or side. Team modules' references to them are still checked. You don't need to check a platform module's references.

## 3. Write the Model

Save the model as `os11-audit/architecture-canvas.json` in the current working directory (create the folder if needed):

```json
{
  "title": "Architecture Canvas: Orders_UI",
  "audited": "Orders_UI",
  "modules": [
    { "name": "Orders_UI", "layer": "end-user", "sublayer": "End User", "references_checked": true },
    { "name": "Order_BL", "layer": "core", "sublayer": "Composite Logic", "references_checked": true },
    { "name": "Order_CS", "layer": "core", "sublayer": "Core Service" },
    { "name": "Payment_IS", "layer": "foundation", "sublayer": "Foundation Service", "references_checked": true },
    { "name": "OutSystemsUI", "layer": "foundation", "sublayer": "Style Guide", "owner": "platform" }
  ],
  "references": [
    { "from": "Orders_UI", "to": "Order_BL" },
    { "from": "Orders_UI", "to": "OutSystemsUI" },
    { "from": "Order_BL", "to": "Order_CS" },
    { "from": "Order_BL", "to": "Payment_IS" }
  ],
  "omitted": []
}
```

- `layer` and `sublayer` must match the table exactly (`end-user`, `core`, `foundation`; sub-layer names as written).
- `references_checked` (default `false`; the audited module counts as checked) says whether you recorded that module's own references.
- `owner` is `team` (the default) or `platform`.
- `audited` and `omitted` are optional.
- A complete example is in [../assets/example-canvas.json](../assets/example-canvas.json).

## 4. Render

Run the script from this skill's directory with Python 3.8 or later (no packages needed). Use `python3` on macOS and Linux, and `py -3` or `python` on Windows:

```bash
python3 <skill-directory>/scripts/render_canvas.py os11-audit/architecture-canvas.json os11-audit/architecture-canvas.svg --html os11-audit/architecture-canvas.html
```

Leave out `--html os11-audit/architecture-canvas.html` only when you know you can't publish or open an HTML page.

The script:

- **Validates** the model and exits with an `error:` line if a layer, sub-layer, owner, or reference is invalid. Fix the JSON and run it again.
- **Detects violations** itself:
  - `upward`: a team module referencing a module in a higher layer.
  - `side`: a team End User module referencing another End User module.
  - `cycle`: every reference that is part of a dependency cycle, direct or indirect, in any layer. Side references inside Core and Foundation are allowed unless they are part of a cycle.
- **Groups cycles** as `C1`, `C2`, and so on: each group is a set of modules that all reach each other. For each group it prints every distinct path, and the references in it that point up the canvas order (for example a Core Service module referencing Composite Logic). Those are usually the references to remove.
- **Numbers every violation.** The diagram puts the number on the reference and lists the violations, cycles, and gaps below the canvas, so the arrows carry no text. Compliant references are drawn thin and grey so the violations stand out.
- **Writes a focused diagram** when the model has more than 15 modules: `architecture-canvas-focus.svg`, next to the full one, with the audited module, the modules it references or is referenced by, and every module in a violation or cycle. Violation numbers match the full diagram.
- **Writes the interactive diagram** with `--html`: a copy of the template with the model embedded in it.
- **Prints a plain-text summary** of the canvas, violations, cycles, and gaps.

Every upward or side violation the script prints must have a matching `[ARCH-###]` finding, and every cycle group must have one finding that lists its paths. Every upward, side, or cycle finding must appear in the script's output. If they disagree, correct the model or the findings before you finish.

If Python is not available, say so and keep the JSON file. When you can publish an Artifact, fill the template by hand (section 6) and publish it, since the page computes the violations itself. Otherwise tell the user they can render the diagram later with the command above. Either way, report the reference violations from your own analysis, and check them against the page if you published one.

## 5. Show It

- **As an Artifact (primary, when you can publish one)**: publish `os11-audit/architecture-canvas.html` exactly as the script wrote it, with whatever Artifact tool you have (for example the `Artifact` tool with `file_path` set to that file). Don't edit the page, restyle it, or rebuild it in another format: its analysis is tested against the script's. If the tool needs a title, use the model's `title`; if it asks for a description, use "OutSystems 11 Architecture Canvas with numbered upward, side, and cycle violations." Republish the same file when you re-run the audit, so the link stays the same. The page shows the canvas, the numbered violations, every cycle with its paths, and the gaps. Hovering or selecting a module traces its references, selecting a violation or cycle highlights it, compliant references can be hidden, and models with more than 15 modules open in the focused view with a switch to the full canvas.
- **In the audit output**: under `## Architecture Canvas Diagram`, link the Artifact if you published one, give the SVG path, embed it with `![Architecture Canvas](os11-audit/architecture-canvas.svg)`, and paste the script's text summary in a `text` code block. If the script wrote a focused diagram, embed it first with `![Architecture Canvas, focused](os11-audit/architecture-canvas-focus.svg)` and link the full one under it. Terminals show the summary; Markdown viewers show the image.
- **In the final report**: the `os11-audit-report` skill embeds the same SVGs, since a Markdown report can't embed an Artifact. It links the Artifact if there is one.

## 6. Filling the Template Without Python

Only when Python isn't available: copy [../assets/canvas-artifact.html](../assets/canvas-artifact.html) to `os11-audit/architecture-canvas.html` without changing anything else, and make two replacements:

1. Replace the line `__CANVAS_MODEL__` (inside `<script type="application/json" id="canvas-model">`) with the JSON model. Write `<` as `\u003c` in any string so the model can't close the script element.
2. Replace `<title>Architecture Canvas</title>` with the model's title.

The page validates the model when it opens. If the model is invalid it shows the error instead of a diagram; fix the JSON and fill the template again.
