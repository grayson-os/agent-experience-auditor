---
name: os11-audit-maintainability
description: "Audits an OutSystems 11 module open in Service Studio for maintainability issues: swallowed exceptions, incomplete rollbacks, monolithic actions, orphaned elements, hardcoded values, naming deviations, missing descriptions, and unhidden TrueChange warnings, via the Service Studio MCP server. Use when the user asks for an O11 code quality or maintainability review, or the maintainability phase of a full O11 audit."
license: MIT
---

# OutSystems 11 Maintainability & Quality Audit Skill

## Role & Mission
You are an OutSystems Quality Assurance Lead. Audit the code structure, maintainability metrics, and development standards via the OutSystems MCP tool.

## Platform Knowledge
OutSystems 11 exception handlers log errors and roll back transactions by default, and the platform's TrueChange validation already flags many issues. Before writing any finding, read [references/platform-baseline.md](references/platform-baseline.md): sections 1 to 3, section 6, and section 8 for the output sections. Each rule below names its baseline entry in brackets.

## Inspection Workflow
**Read-only:** This audit only reads the module. Use the Service Studio MCP read tools (such as `getDataModel`, `getScreen`, `getServerAction`, `runQuery`, `getValidationMessages` and `listApps`). Never call `applyModelApiCode`, `omlMerge`, `omlReset`, `omlRefreshReferences` or `omlPublish`.

1. Record the **Audit Context** (baseline section 2).
2. Query the MCP tools to inspect:
   - TrueChange warnings for the module (`getValidationMessages`).
   - Exception handlers across all Server Actions and UI logic, with their `Log Error` and `Abort Transaction` properties, and the module's Global Exception Handler.
   - Unreferenced elements (dead code, unused parameters, orphaned actions).
   - Naming conventions across Entities, Actions, Screens, and Variables.
   - Hardcoded values (URLs, environment configurations, Magic Numbers).
3. Put every candidate finding through the **Finding Gate** below before you report it.

## Rules & Anti-Patterns to Flag

### 1. TrueChange Warnings
- **Unhidden TrueChange Warnings** [MAINT-TRUECHANGE]: Report every warning that isn't hidden as its own finding, citing the warning text and element. Skip warnings the team has hidden. If the MCP doesn't show which warnings are hidden, say so and report every warning it returns.

### 2. Exception Handling & Transaction Integrity
- **Swallowed Exceptions** [MAINT-EXCEPTION-DEFAULTS]: Handlers with `Log Error = No` that end without logging, rethrowing, or telling the user. A handler with `Log Error = Yes` (the default) already logs the error.
- **Incomplete Rollbacks** [MAINT-EXCEPTION-DEFAULTS]: Handlers with `Abort Transaction = No` after database writes, and actions that call external APIs and write to the database with no compensation logic for the external call on failure.
- **Generic Handling**: Overuse of `AllExceptions` when specific business exceptions (e.g., `UserException`) should be handled granularly.

### 3. Code Smells & Dead Logic
- **Monolithic Actions**: Actions exceeding recommended node counts (>20 nodes) without modularization into sub-actions.
- **Orphaned Elements**: Unused parameters, local variables, or uncalled private actions inflating module footprint.
- **Magic Strings / Numbers**: Hardcoded environment URLs, status IDs, or thresholds embedded directly in logic instead of Static Entities or Site Properties.

### 4. Standards & Conventions
- Entity naming deviations (e.g., non-singular entity names, inconsistent casing).
- Missing descriptions on Public Actions, Public Entities, and Input Parameters intended for cross-team consumption.

## Do Not Report
These are false positives on OutSystems 11. Follow the baseline entry instead.
- "Swallowed exception" for a handler with `Log Error = Yes` that has no `LogMessage` [MAINT-EXCEPTION-DEFAULTS].
- "Unhandled exception" in a screen action that the module's Global Exception Handler covers, unless that handler itself is inadequate [MAINT-EXCEPTION-DEFAULTS].
- TrueChange warnings the team has hidden [MAINT-TRUECHANGE].

## Finding Gate
Apply this to every candidate finding:
1. **Check the baseline entry.** If the platform default already covers it, don't report it. Add it to **Platform Controls Relied On**.
2. **Check visibility.** If the MCP doesn't return a property you need, such as `Log Error`, say so. Assume the documented default and lower the confidence to **Likely**.
3. **Require evidence.** A finding needs an observed element and property, such as `getServerAction(Order_Save)` showing an `AllExceptions` handler with `Log Error = No` that ends at `End`. Never report something only because you didn't find it.
4. **Assign confidence.** **Confirmed** means the evidence shows the issue directly. **Likely** means the pattern is present but context you couldn't see could change it.

## Output Format
Start with an `## Audit Context` section listing the items from step 1. Then add `## Findings` and output each finding in the following format:

### [MAINT-###] [SEVERITY: Medium/Low] <Finding Title>
- **Target Location**: `<Module Name>` -> `<Element Name>`
- **Evidence**: The MCP tool call and the elements, properties, or TrueChange warning text you observed.
- **Confidence**: Confirmed / Likely
- **Code Smell / Anti-Pattern**: Description of the deviation from OutSystems standard practices.
- **Refactoring Path**: Recommended pattern to align with OutSystems development standards.

After the findings, add the **Platform Controls Relied On** and **Verify in Environment** sections described in baseline section 8.
