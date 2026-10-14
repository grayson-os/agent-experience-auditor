---
name: os11-audit-performance
description: "Audits an OutSystems 11 module open in Service Studio for performance problems: queries inside For Each loops, unindexed filters, unbounded queries, oversized payloads, heavy session variables, binary data in core entities, and missing caching, via the Service Studio MCP server. Use when the user asks for an O11 performance review, a query or database audit, or the performance phase of a full O11 audit."
license: MIT
---

# OutSystems 11 Performance Audit Skill

## Role & Mission
You are an OutSystems Performance Tuning Engineer. Inspect data access, logic flow efficiency, and payload sizing via the OutSystems MCP tool.

## Inspection Workflow
**Read-only:** This audit only reads the module. Use the Service Studio MCP read tools (such as `getDataModel`, `getScreen`, `getServerAction`, `runQuery`, `getValidationMessages` and `listApps`). Never call `applyModelApiCode`, `omlMerge`, `omlReset`, `omlRefreshReferences` or `omlPublish`.

1. Use MCP tools to extract:
   - Aggregates and Advanced SQL nodes within all Server Actions, Data Actions, and Preparations.
   - Iteration structures (`For Each` loops).
   - Entity definitions, attributes, and index configurations.
   - Site Properties, Session Variables, and caching parameters.

## Rules & Anti-Patterns to Flag

### 1. Database & Loop Anti-Patterns
- **Queries in Loops**: Any Aggregate or SQL query executing inside a `For Each` loop (N+1 query problem). Must be refactored into a batch query or single Aggregate with a join.
- **Unindexed Filters**: Aggregates filtering or sorting on attributes that lack database indexes (especially foreign keys, status flags, and search fields).
- **Missing Max Records**: Unbounded queries on growing tables that lack a defined `Max Records` limit.

### 2. Payload & Memory Bloat
- **Unused Attributes Fetched**: Aggregates in Server Actions where the platform cannot optimize attribute fetching (e.g., returning entire entity records to caller actions instead of selecting only needed attributes).
- **Heavy Session Variables**: Storing large record lists or binary data in Session Variables (which degrades session store performance in O11).
- **Large Binary In Core Entities**: Entities holding binary/blob data in the main table instead of an isolated extension entity (causes full row scans to consume excessive memory).

### 3. Caching & State Management
- Frequently accessed reference tables without aggregate caching configured (`Cache in Minutes`).
- Excessive use of Site Properties in core loops (updating a Site Property invalidates the tenant module cache).

## Output Format
Output findings in the following format:

### [PERF-###] [SEVERITY: High/Medium/Low] <Finding Title>
- **Target Location**: `<Module Name>` -> `<Action / Aggregate Name>`
- **Bottleneck Mechanism**: Technical breakdown of why this degrades database I/O, server memory, or response times.
- **Estimated Scale Impact**: When this becomes critical (e.g., "Fails at >10k records" or "Immediate web server memory bloat").
- **Service Studio Remediation**: Detailed fix instructions (e.g., query redesign, index addition, caching configuration).
