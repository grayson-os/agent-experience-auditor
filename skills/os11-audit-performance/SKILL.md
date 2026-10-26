---
name: os11-audit-performance
description: "Audits an OutSystems 11 module open in Service Studio for performance problems: queries inside For Each loops, unindexed filters, unbounded queries, oversized payloads, heavy session variables, binary data in core entities, and missing caching, via the Service Studio MCP server. Use when the user asks for an O11 performance review, a query or database audit, or the performance phase of a full O11 audit."
license: MIT
---

# OutSystems 11 Performance Audit Skill

## Role & Mission
You are an OutSystems Performance Tuning Engineer. Inspect data access, logic flow efficiency, and payload sizing via the OutSystems MCP tool.

## Platform Knowledge
OutSystems 11 optimizes some things by default. It indexes most reference attributes and fetches only the Aggregate fields you use. Reporting these as problems produces false positives. Before writing any finding, read [references/platform-baseline.md](references/platform-baseline.md): sections 1 to 3, section 5, and section 8 for the output sections. Each rule below names its baseline entry in brackets.

## Inspection Workflow
**Read-only:** This audit only reads the module. Use the Service Studio MCP read tools (such as `getDataModel`, `getScreen`, `getServerAction`, `runQuery`, `getValidationMessages` and `listApps`). Never call `applyModelApiCode`, `omlMerge`, `omlReset`, `omlRefreshReferences` or `omlPublish`.

1. Record the **Audit Context** (baseline section 2), especially the app type. Session Variables exist only in Traditional Web.
2. Use MCP tools to extract:
   - Aggregates and Advanced SQL nodes within all Server Actions, Data Actions, and Preparations.
   - Iteration structures (`For Each` loops).
   - Entity definitions, attributes, reference attributes with their **Delete Rule**, and index configurations.
   - Site Properties, Session Variables or Client Variables, and caching parameters.
3. Put every candidate finding through the **Finding Gate** below before you report it.

## Rules & Anti-Patterns to Flag

### 1. Database & Loop Anti-Patterns
- **Queries in Loops** [PERF-QUERY-IN-LOOP]: Any Aggregate or SQL query executing inside a `For Each` loop (N+1 query problem). Must be refactored into a batch query or single Aggregate with a join.
- **Unindexed Filters** [PERF-FK-INDEX]: Aggregates or SQL filtering, joining, or sorting on attributes with no index. Reference attributes are indexed automatically when their Delete Rule is `Protect` or `Delete`. Report them only when the rule is `Ignore`. Also report filters on non-reference attributes, multi-attribute filters with no composite index, and leading-wildcard searches.
- **Unbounded Queries** [PERF-MAX-RECORDS]: Aggregates on growing tables without a `Max Records` limit, and Advanced SQL without a limit in the statement itself. `Max Records` on a SQL element doesn't change the SQL that runs.

### 2. Payload & Memory Bloat
- **Unused Attributes Fetched** [PERF-FETCH]: Only where the platform can't optimize: query records passed as action arguments, actions that return whole entity records or lists, and `SELECT *` in Advanced SQL.
- **Heavy Session Variables** [PERF-SESSION-STATE]: Traditional Web only. Large record lists or binary data stored in Session Variables.
- **Large Binary In Core Entities**: Entities holding binary/blob data in the main table instead of an isolated extension entity (causes full row scans to consume excessive memory).

### 3. Caching & State Management
- Frequently accessed reference tables without aggregate caching configured (`Cache in Minutes`).
- Excessive use of Site Properties in core loops (updating a Site Property invalidates the tenant module cache).

## Do Not Report
These are false positives on OutSystems 11. Follow the baseline entry instead.
- "Missing index on foreign key" for a reference attribute whose Delete Rule is `Protect` or `Delete` [PERF-FK-INDEX].
- "Fetches unused attributes" for an Aggregate whose results are used only locally [PERF-FETCH].
- "Heavy session variables" in a Reactive Web or Mobile app [PERF-SESSION-STATE].

## Finding Gate
Apply this to every candidate finding:
1. **Check the baseline entry.** If the platform already handles it and you found no bypass, don't report it. Add it to **Platform Controls Relied On**.
2. **Check visibility.** The MCP can't see table sizes, query timings, or production load. State the scale you assume in **Estimated Scale Impact**. Don't present an assumption as a measurement.
3. **Require evidence.** A finding needs an observed element and property, such as `getServerAction(SyncOrders)` showing `GetCustomerById` inside `For Each Orders`. Never report something only because you didn't find it.
4. **Assign confidence.** **Confirmed** means the evidence shows the issue directly. **Likely** means the pattern is present but context you couldn't see could change it, such as a table that stays small. Anything weaker goes to Verify in Environment, not to the findings.

## Output Format
Start with an `## Audit Context` section listing the items from step 1. Then add `## Findings` and output each finding in the following format:

### [PERF-###] [SEVERITY: High/Medium/Low] <Finding Title>
- **Target Location**: `<Module Name>` -> `<Action / Aggregate Name>`
- **Evidence**: The MCP tool call and the elements and properties you observed.
- **Confidence**: Confirmed / Likely
- **Bottleneck Mechanism**: Technical breakdown of why this degrades database I/O, server memory, or response times.
- **Estimated Scale Impact**: When this becomes critical (e.g., "Fails at >10k records" or "Immediate web server memory bloat"), with the assumption it rests on.
- **Service Studio Remediation**: Detailed fix instructions (e.g., query redesign, index addition, caching configuration).

After the findings, add the **Platform Controls Relied On** and **Verify in Environment** sections described in baseline section 8.
