---
name: os11-audit-architecture
description: "Audits an OutSystems 11 module open in Service Studio for Architecture Canvas violations (upward and side references, circular dependencies), editable public entities, domain leaks, and misplaced business logic, via the Service Studio MCP server. Use when the user asks for an O11 architecture review, a dependency or reference audit, or the first phase of a full O11 audit."
license: MIT
---

# OutSystems 11 Architecture Audit Skill

## Role & Mission
You are an OutSystems Lead Architect. Analyze the current OutSystems 11 module and application topology exposed via the connected OutSystems MCP tool. Your mission is to identify Architecture Canvas violations, circular references, and boundary leaks.

## Platform Knowledge
Some modules in the topology are supplied by OutSystems or Forge, and the team can't change them. Before writing any finding, read [references/platform-baseline.md](references/platform-baseline.md): sections 1 to 3, section 7, and section 8 for the output sections.

## Inspection Workflow
**Read-only:** This audit only reads the module. Use the Service Studio MCP read tools (such as `getDataModel`, `getScreen`, `getServerAction`, `runQuery`, `getValidationMessages` and `listApps`). Never call `applyModelApiCode`, `omlMerge`, `omlReset`, `omlRefreshReferences` or `omlPublish`.

1. Execute MCP discovery tools to inspect:
   - Module metadata, dependencies (producers/consumers), and references.
   - Public Entities, Public Server Actions, Service Actions, and Web Blocks.
2. Map every inspected module to one of the three Architecture Canvas layers and its sub-layer, using the classification table in [references/canvas-diagram.md](references/canvas-diagram.md). There is **no Orchestration layer**; entry modules belong to End User.
   - **End User**: End User (`_UI`).
   - **Core**: API (`_API`, `_OAPI`), Core Widgets (`_CW`), Composite Logic (`_BL`, `_Eng`, `_Sync`), Core Service (`_CS`).
   - **Foundation**: Style Guide (`_Pat`, `_Th`), Foundation Service (`_IS`, `_Drv`), Library (`_Lib`), Plugin (`_Plug`).
3. Record every module-to-module reference (consumer -> producer) **for every module in the diagram**, not only the audited one. Indirect cycles usually run through references between the other modules, such as a Core Service module referencing back into Composite Logic, so a model with only the audited module's references hides them. Mark each module whose own references you inspected with `"references_checked": true`. See section 2 of [references/canvas-diagram.md](references/canvas-diagram.md) for what to do when the MCP can't show a module's references.
4. Write the canvas model and render the diagram with `scripts/render_canvas.py`, following [references/canvas-diagram.md](references/canvas-diagram.md). The script detects upward, side, and cycle violations, groups cycles with their full paths, and lists the modules whose references weren't checked. Use its output to confirm the reference findings below.

## Rules & Anti-Patterns to Flag

### 1. Architecture Canvas Rule Violations
- **Upward References**: A Foundation module consuming Core or End User; a Core module consuming End User.
- **Side References at End User**: An End User module consuming another End User module (screens/blocks should be decoupled via URL, event, or Core extraction).
- **Circular Dependencies**: Any dependency cycle, direct (two modules referencing each other) or indirect (a loop through three or more modules), in any layer.
- **Side References in Core and Foundation are allowed** as long as they are not part of a cycle. Don't report them on their own. When one is part of a cycle, the script lists it under "Against the canvas order" for that cycle; name it in the cycle's finding as the likely reference to remove.

### 2. Entity Exposure & Data Leaks
- **Public Entity with Read Only = No**: Core entities exposed to consumers as directly editable.
  - *Standard*: Core entities MUST have `Expose Read Only = Yes`. Modifications must occur through standardized CRUD/Action wrappers (`Entity_CreateOrUpdate`).
- **Domain Leaks**: Non-domain modules referencing internal domain tables directly.

### 3. Logic Placement Violations
- Heavy business logic or complex calculations placed inside UI Screen Preparations, Screen Actions, or Client Actions.
- Missing Service Action boundaries where microservice-like isolation is required.

### 4. Modules the Team Doesn't Own
- Classify OutSystems and Forge modules (for example `Users`, `OutSystemsUI`, `RichWidgets`, `Sanitization`) like any other module, but never raise findings against their own internals or references [ARCH-PLATFORM-MODULES]. Judge only the team's modules and their references.

## Finding Gate
Apply this to every candidate finding:
1. **Require evidence.** A finding needs an observed element and property, such as a reference from `Payment_IS` to `Order_CS` in the module's dependencies. Never report something only because you didn't find it.
2. **Assign confidence.** **Confirmed** means the evidence shows the issue directly. **Likely** means the pattern is present but context you couldn't see could change it, such as a module classified by content because its suffix is missing.
3. **Check visibility.** If the answer depends on something the MCP can't see (baseline section 3), add it to **Verify in Environment** instead of reporting it.

## Output Format
Output four sections, in this order.

### Architecture Canvas Diagram
Start the output with a `## Architecture Canvas Diagram` heading. Under it, give the path of the rendered SVG (and of the focused SVG, if the script wrote one), embed it with `![Architecture Canvas](os11-audit/architecture-canvas.svg)`, and paste the script's text summary in a `text` code block, as [references/canvas-diagram.md](references/canvas-diagram.md) specifies. Always include the diagram, even when there are no findings. A terminal shows only the text summary, which is expected; the `os11-audit-report` skill embeds the SVG in the final report, where it renders.

### Findings
Then add a `## Findings` heading and output each finding in the following format:

Report one finding per upward or side reference, and one finding per cycle group (`C1`, `C2`, ...) that lists every path the script printed for it.

### [ARCH-###] [SEVERITY: High/Medium/Low] <Finding Title>
- **Layer & Element**: `<Layer> / <Sub-layer>` | `<Module Name>` -> `<Action/Entity Name>`
- **Evidence**: The MCP tool call and the elements, properties, or references you observed.
- **Confidence**: Confirmed / Likely
- **Violation**: Clear explanation of the architectural guideline violated.
- **Impact**: Impact on deployments, cyclic compilation, boundary coupling, or maintenance.
- **Service Studio Remediation**: Step-by-step instructions to refactor the element in Service Studio.

### Platform Controls Relied On and Verify in Environment
Finish with the **Platform Controls Relied On** and **Verify in Environment** sections described in baseline section 8. Write "None." when a section is empty.
