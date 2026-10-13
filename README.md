# OutSystems 11 Agentic Review Suite (MCP)

An automated, phased code quality and architectural review toolkit for OutSystems 11 (O11). This repository packages specialized Model Context Protocol (MCP) audit skills that interface directly with OutSystems Service Studio to inspect active eSpace modules across five pillars: Architecture, Security, Performance, Maintainability, and Executive Reporting.

## Purpose

Traditional code reviews and manual Code Quality triages often happen late in the development lifecycle or miss nuanced logic flows (such as unescaped inline SQL parameters, aggregates inside loops, or upward architectural violations).

This toolkit provides:
- **Direct Service Studio Inspection**: Interrogates module metadata, logic flows, entities, and dependencies in real time via the OutSystems Agent Experience MCP server.
- **Context-Preserving Multi-Turn Analysis**: Splits audits into five discrete markdown skills to prevent LLM context-window degradation and hallucinations.
- **Actionable Remediation**: Produces structured findings with explicit Service Studio fix instructions rather than generic advice.

## Repository Structure

```text
.
├── README.md
└── .agent/
    └── skills/
        ├── 01-audit-architecture.md     # Canvas layers, references, boundary leaks
        ├── 02-audit-security.md         # OWASP, RBAC checks, injection vulnerabilities
        ├── 03-audit-performance.md      # Database I/O, queries in loops, caching
        ├── 04-audit-maintainability.md  # Exception handling, dead logic, conventions
        └── 05-audit-synthesizer.md      # Aggregates findings into executive client deliverables
```

## Prerequisites

1. **OutSystems 11 Service Studio**: Version supporting the OutSystems Agent Experience MCP endpoint.
2. **Coding Agent / Client Supporting MCP**
3. An active OutSystems 11 environment connection inside Service Studio.

## Installation & Setup

### 1. Enable OutSystems MCP in Service Studio
1. Open **Service Studio**.
2. Navigate to **Preferences** (or **Experimental Features** / **Agent Experience**, depending on your release build).
3. Enable the **Agent Experience MCP Server**. Note the local loopback port (default is typically `127.0.0.1:PORT/mcp` or a named pipe).

### 2. Configure Your Agent Client

#### For Cursor (`~/.cursor/mcp.json` or project `.cursor/mcp.json`)
Add the OutSystems MCP server entry:

```json
{
  "mcpServers": {
    "outsystems-local": {
      "url": "http://127.0.0.1:PORT/mcp"
    }
  }
}
```
*(Replace `PORT` with the actual port shown in Service Studio).*

#### For Claude Code CLI (`~/.claude.json` or project configuration)
```bash
claude mcp add outsystems-local http://127.0.0.1:PORT/mcp
```

### 3. Clone This Repository
Clone or copy this folder structure into your local working workspace:

```bash
git clone <your-repo-url> outsystems-audit-agent
cd outsystems-audit-agent
```

## Usage Instructions

Always ensure the target modules (`.oml`) are **open in Service Studio** before running any audit skill. The MCP server reads from the active module state.

### Phase-by-Phase Execution

Run each audit phase in an isolated prompt or agent session to preserve model context:

#### Step 1: Architecture Review
In your agent chat interface:
```text
@01-audit-architecture.md Run the Architecture Audit on the currently open module and output all findings.
```

#### Step 2: Security Review
In a new or continuing session:
```text
@02-audit-security.md Run the Security Audit on the open module. Focus on exposed endpoints, injection risks, and role authorization.
```

#### Step 3: Performance Review
```text
@03-audit-performance.md Inspect queries, loop executions, table indexes, and payload allocations on the open module.
```

#### Step 4: Maintainability Review
```text
@04-audit-maintainability.md Evaluate exception handling paths, naming standards, and unreferenced/orphaned elements.
```

#### Step 5: Report Synthesis
Feed the outputs from Steps 1–4 into the synthesizer skill:
```text
@05-audit-synthesizer.md Compile all previously generated audit findings into the final client deliverable report.
```

## Expected Outputs

### 1. Granular Technical Findings (Steps 1–4)
Each audit skill produces standardized findings using unique tracking IDs and structured metadata:

```markdown
### [SEC-004] [SEVERITY: High] Unchecked Role Authorization on Public Action
- **Vulnerability Category**: Broken Function Level Authorization
- **Target Location**: Order_CS -> Action: Order_PurgeArchivedRecords
- **Exploitation Vector**: Action is flagged as Public with Expose Read Only = No logic, but lacks a CheckAdminRole check or tenant-boundary validation.
- **Service Studio Remediation**: 
  1. Open Order_CS > Logic > Server Actions > Order_PurgeArchivedRecords.
  2. Drag a CheckRole action into the flow prior to the SQL execution node.
  3. Raise a SecurityException if CheckAdminRole.HasRole is False.
```

### 2. Consolidated Executive Report (Step 5)
The synthesis phase outputs a Markdown document containing:
- **Executive Summary & Risk Distribution Matrix**: Quantified count of Critical, High, Medium, and Low risks by pillar.
- **Prioritized Roadmap**: Sequenced checklist of mandatory refactors based on risk severity and implementation effort.
- **Detailed Remediation Catalog**: Fully expanded technical findings grouped by pillar for developer handover.
- **Platform Recommendations**: Systemic improvements (e.g., CI/CD governance, Code Quality rules, design system alignment).

## What to Do with the Outputs

```text
[Generated Audit Report]
          │
          ├──► 1. Triage & Stakeholder Presentation (Architecture & PM)
          │
          ├──► 2. Backlog Item Generation (Jira / Azure DevOps)
          │
          ├──► 3. Developer Remediation in Service Studio
          │
          └──► 4. Verification & Regression Re-run via MCP
```

### 1. Triage and Risk Calibration
- **Review Critical/High Items**: Focus first on `[SEC-###]` and `[ARCH-###]` findings with `High` or `Critical` severity. Confirm whether flagged SQL queries or exposed actions have compensating controls outside the inspected module (e.g., API Gateway policies, enterprise network restrictions).
- **Check False Positives**: Verify if an unindexed filter attribute runs against a table guaranteed to remain under 100 rows (e.g., a non-changing configuration table).

### 2. Ticket Creation & Backlog Integration
Convert each finding into a task or bug in your tracking tool (e.g., Jira, Azure DevOps):
- **Title**: `[Pillar] <Finding Title>` (e.g., `[Performance] Move Aggregate_GetUserData out of For Each loop`).
- **Description**: Copy the `Target Location`, `Mechanism / Impact`, and `Service Studio Remediation` sections directly into the ticket description.
- **Story Points / Priority**: Map `High Severity` findings to Sprint Blockers or Next-Sprint Tech Debt.

### 3. Implementation in Service Studio
Assign findings to developers. Developers can open the affected module in Service Studio and follow the exact path provided in the remediation steps:
- Replace inline parameters with parameterized values or `EncodeSql()`.
- Add missing database indexes via the Entity definition.
- Refactor circular references by moving shared entities down into a Core (`_CS`) or Foundation library module.

### 4. Verification Run
After 1-Click Publishing the remediations in Service Studio:
- Re-run the specific skill file (e.g., `@03-audit-performance.md`) against the modified module.
- Confirm that the previously flagged issues no longer appear in the agent output before marking work as resolved.
