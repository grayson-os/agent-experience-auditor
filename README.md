# OutSystems 11 Agentic Review Suite (MCP)

An automated, phased code quality and architectural review toolkit for OutSystems 11 (O11). This repository packages five [Agent Skills](https://agentskills.io) that use the [OutSystems 11 MCP](https://github.com/OutSystems/outsystems11-mcp) server embedded in Service Studio to inspect the module you have open across five pillars: Architecture, Security, Performance, Maintainability, and Executive Reporting.

## Purpose

Traditional code reviews and manual Code Quality triages often happen late in the development lifecycle or miss nuanced logic flows (such as unescaped inline SQL parameters, aggregates inside loops, or upward architectural violations).

This toolkit provides:
- **Direct Service Studio Inspection**: Interrogates module metadata, logic flows, entities, and dependencies in real time through the Service Studio MCP server, part of [OutSystems Agent Experience](https://www.outsystems.com/platform/agent-experience).
- **Context-Preserving Multi-Turn Analysis**: Splits audits into five discrete skills to prevent LLM context-window degradation and hallucinations.
- **Actionable Remediation**: Produces structured findings with explicit Service Studio fix instructions rather than generic advice.
- **Read-Only Audits**: The audit skills use only the MCP read tools and never modify, merge, or publish your module.

## Included Skills

| Skill | Phase | What it checks |
| :--- | :--- | :--- |
| `os11-audit-architecture` | 1 | Architecture Canvas layers, upward/side/circular references, entity exposure, logic placement |
| `os11-audit-security` | 2 | Role checks on public actions, multi-tenancy, SQL injection, XSS, unauthenticated APIs, sensitive data |
| `os11-audit-performance` | 3 | Queries in loops, indexes, unbounded queries, payload size, session state, caching |
| `os11-audit-maintainability` | 4 | Exception handling, dead code, monolithic actions, hardcoded values, naming |
| `os11-audit-report` | 5 | Combines the findings from phases 1–4 into an executive client report |

## Repository Structure

```text
.
├── .claude-plugin/
│   ├── plugin.json         # Claude Code plugin manifest (holds the release version)
│   └── marketplace.json    # Lets Claude Code install the plugin straight from this repo
├── .github/workflows/
│   └── release.yml         # Publishes a GitHub release for each vX.Y.Z tag
├── skills/
│   ├── os11-audit-architecture/SKILL.md     # Canvas layers, references, boundary leaks
│   ├── os11-audit-security/SKILL.md         # OWASP, RBAC checks, injection vulnerabilities
│   ├── os11-audit-performance/SKILL.md      # Database I/O, queries in loops, caching
│   ├── os11-audit-maintainability/SKILL.md  # Exception handling, dead logic, conventions
│   └── os11-audit-report/SKILL.md           # Aggregates findings into executive client deliverables
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## Prerequisites

1. **Service Studio 11.55.91 or later**, which embeds the OutSystems 11 MCP server. See the [OutSystems 11 MCP documentation](https://success.outsystems.com/documentation/11/outsystems_mcp/).
2. **An MCP-compatible coding agent**, such as Claude Code, Cursor, GitHub Copilot, Codex, Kiro, or Google Antigravity.
3. **Node.js** (for `npx`), only if you install with the cross-agent installer.

## Installation

Installation has two parts: connect your agent to the Service Studio MCP server, then install the skills.

### 1. Start the MCP Server in Service Studio

The server does not start automatically. Start it each session from the module you want to audit:

1. Open the module in Service Studio.
2. Go to **Edit > MCP Configuration...**.
3. Confirm the **MCP server port** (default `41820`) and click **Start MCP Server**.

The dialog shows the server URL. If port `41820` is taken, Service Studio picks another port, so use the URL the dialog shows in the steps below.

### 2. Register the MCP Server in Your Agent

**Claude Code:**

```bash
claude mcp add --transport http servicestudio http://127.0.0.1:41820/mcp --scope user
```

**Cursor** (`.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` for all projects):

```json
{
  "mcpServers": {
    "servicestudio": {
      "url": "http://127.0.0.1:41820/mcp"
    }
  }
}
```

**Other agents:** follow the per-agent guides in the official [OutSystems/outsystems11-mcp setup docs](https://github.com/OutSystems/outsystems11-mcp/tree/main/setup-docs).

The first time your agent calls the server, Service Studio shows an **Allow AI agent to connect?** prompt. Approve it only for a session you started.

> **Recommended:** also install the official [`servicestudio-mcp-oml`](https://github.com/OutSystems/outsystems11-mcp) skill. It teaches your agent the Service Studio MCP tool catalog, which helps the audits call the right read tools.

### 3. Install the Audit Skills

#### Claude Code (plugin)

In a Claude Code session (version 2.1.275 or later):

```text
/plugin install os11-audit --marketplace grayson-os/agent-experience-auditor
```

Or from your shell, on any version that supports plugins:

```bash
claude plugin marketplace add grayson-os/agent-experience-auditor
claude plugin install os11-audit@agent-experience-auditor
```

Restart Claude Code, then run `/plugin` to confirm `os11-audit` is installed with five skills. If you have no GitHub SSH key and the install fails, set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` and try again.

#### Cursor, Copilot, Codex, Kiro, and Other Agents

Use the cross-agent [`skills`](https://github.com/vercel-labs/skills) installer, which writes the skills to the right folder for each agent:

```bash
# Current project only
npx skills add grayson-os/agent-experience-auditor

# All projects for one agent (for example, Cursor)
npx skills add grayson-os/agent-experience-auditor -g -a cursor
```

Start a new agent session afterward. Agents discover skills only when a session starts.

#### Manual Install

Download the `os11-audit-skills-vX.Y.Z.zip` asset from the [latest release](https://github.com/grayson-os/agent-experience-auditor/releases/latest) and copy each folder under `skills/` into your agent's skills directory, keeping the folder names unchanged:

| Agent | Project path | Global path |
| :--- | :--- | :--- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` or `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `.agents/skills/` | `~/.codex/skills/` |
| Kiro | `.kiro/skills/` | `~/.kiro/skills/` |

## Updating

Each release is a `vX.Y.Z` git tag with a matching [GitHub release](https://github.com/grayson-os/agent-experience-auditor/releases) and [CHANGELOG](CHANGELOG.md) entry.

| Installed with | Update command |
| :--- | :--- |
| Claude Code plugin | `claude plugin marketplace update agent-experience-auditor`, then `claude plugin update os11-audit@agent-experience-auditor`, then restart Claude Code |
| `npx skills` | `npx skills update` (add `-g` for global installs) |
| Manual copy | Download the new release zip and replace the folders |

Claude Code users can also turn on automatic updates: run `/plugin`, open **Marketplaces**, select `agent-experience-auditor`, and choose **Enable auto-update**.

### Pinning a Release

To stay on one version instead of tracking the latest release, install from its tag:

```bash
# Claude Code
claude plugin marketplace add grayson-os/agent-experience-auditor#v1.0.0

# Other agents
npx skills add https://github.com/grayson-os/agent-experience-auditor/tree/v1.0.0
```

To move to a newer pinned version, remove the old install and repeat with the new tag.

## Usage Instructions

Always ensure the target module (`.oml`) is **open in Service Studio with its MCP server started** before running any audit skill. The MCP server reads from the active module state.

### Phase-by-Phase Execution

Run each audit phase in an isolated agent session to preserve model context. In Claude Code, invoke a skill with `/os11-audit:<skill-name>`. In other agents, invoke it with `/<skill-name>` where supported, or name the skill in your prompt.

#### Step 1: Architecture Review
```text
/os11-audit:os11-audit-architecture Run the Architecture Audit on the currently open module and output all findings.
```

#### Step 2: Security Review
```text
/os11-audit:os11-audit-security Run the Security Audit on the open module. Focus on exposed endpoints, injection risks, and role authorization.
```

#### Step 3: Performance Review
```text
/os11-audit:os11-audit-performance Inspect queries, loop executions, table indexes, and payload allocations on the open module.
```

#### Step 4: Maintainability Review
```text
/os11-audit:os11-audit-maintainability Evaluate exception handling paths, naming standards, and unreferenced/orphaned elements.
```

#### Step 5: Report Synthesis
Feed the outputs from Steps 1–4 into the report skill:
```text
/os11-audit:os11-audit-report Compile all previously generated audit findings into the final client deliverable report.
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
- Re-run the specific audit skill (e.g., `os11-audit-performance`) against the modified module.
- Confirm that the previously flagged issues no longer appear in the agent output before marking work as resolved.

## Releasing (Maintainers)

Claude Code only delivers an update when the `version` in `.claude-plugin/plugin.json` changes, so every release needs a version bump.

1. Bump `version` in `.claude-plugin/plugin.json` following [Semantic Versioning](https://semver.org/).
2. Add a `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md`.
3. Run `claude plugin validate --strict .` and fix anything it reports.
4. Commit, then tag and push: `git tag vX.Y.Z && git push origin main vX.Y.Z`.

The [release workflow](.github/workflows/release.yml) checks that the tag matches `plugin.json`, validates the plugin and skills, and publishes a GitHub release with the changelog notes and a zip of the skills.

## License

Released under the [MIT License](LICENSE).
