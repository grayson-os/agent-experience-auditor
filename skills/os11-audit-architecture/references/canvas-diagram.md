# Architecture Canvas Diagram Specification

Draw the module topology on the OutSystems Architecture Canvas by writing a small JSON model and rendering it with `scripts/render_canvas.py`. The script lays the canvas out as three full-width layers stacked in a single column (End User, Core, Foundation), splits each layer into its sub-layers, draws every reference, and highlights violations.

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
- **References**: one entry per module-to-module reference, from the consumer to the producer. Do not add one entry per element.

## 3. Write the Model

Save the model as `os11-audit/architecture-canvas.json` in the current working directory (create the folder if needed):

```json
{
  "title": "Architecture Canvas: Orders_UI",
  "audited": "Orders_UI",
  "modules": [
    { "name": "Orders_UI", "layer": "end-user", "sublayer": "End User" },
    { "name": "Order_BL", "layer": "core", "sublayer": "Composite Logic" },
    { "name": "Order_CS", "layer": "core", "sublayer": "Core Service" },
    { "name": "Payment_IS", "layer": "foundation", "sublayer": "Foundation Service" }
  ],
  "references": [
    { "from": "Orders_UI", "to": "Order_BL" },
    { "from": "Order_BL", "to": "Order_CS" },
    { "from": "Order_BL", "to": "Payment_IS" }
  ],
  "omitted": []
}
```

- `layer` and `sublayer` must match the table exactly (`end-user`, `core`, `foundation`; sub-layer names as written).
- `audited` and `omitted` are optional.
- A complete example is in [../assets/example-canvas.json](../assets/example-canvas.json).

## 4. Render

Run the script from this skill's directory with Python 3.8 or later (no packages needed). Use `python3` on macOS and Linux, and `py -3` or `python` on Windows:

```bash
python3 <skill-directory>/scripts/render_canvas.py os11-audit/architecture-canvas.json os11-audit/architecture-canvas.svg
```

The script:

- **Validates** the model and exits with an `error:` line if a layer, sub-layer, or reference is invalid. Fix the JSON and run it again.
- **Detects violations** itself: `upward` (a module referencing a module in a higher layer), `side` (an End User module referencing another End User module), and `cycle` (any reference inside a dependency cycle).
- **Writes the SVG** and prints a plain-text summary of the canvas and its violations.

Every violation the script prints must have a matching `[ARCH-###]` finding, and every upward, side, or cycle finding must appear in the script's output. If they disagree, correct the model or the findings before you finish.

If Python is not available, say so, keep the JSON file, and tell the user they can render it later with the command above. Report the reference violations from your own analysis instead.

## 5. Show It

- **In the audit output**: under `## Architecture Canvas Diagram`, give the SVG path, embed it with `![Architecture Canvas](os11-audit/architecture-canvas.svg)`, and paste the script's text summary in a `text` code block. Terminals show the summary; Markdown viewers show the image.
- **In the final report**: the `os11-audit-report` skill embeds the same SVG.
