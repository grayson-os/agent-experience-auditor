# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/), and each version matches a `vX.Y.Z` tag and GitHub release.

## [1.1.0] - Unreleased

### Added

- `os11-audit-architecture` now renders an Architecture Canvas diagram (SVG) of module references across the End User, Core, and Foundation layers and their sub-layers, with upward, side, and cycle violations detected and highlighted.
- `os11-audit-report` embeds the diagram in a new "Architecture Canvas Map" section.
- The Canvas diagram groups cycles (`C1`, `C2`, ...) and lists each one's full path, direct or indirect, plus the references in it that point up the canvas order. Cycles are drawn in purple, separate from upward and side references.
- The architecture audit records the references of every module in the diagram, not only the audited one, and marks modules whose references it couldn't check. The diagram and summary list those modules, since cycles through them can't be ruled out.
- Modules marked `"owner": "platform"` (OutSystems and Forge) are drawn dashed, and their own references are never flagged.
- For more than 15 modules, the script also writes a focused diagram with the audited module, its direct references, and every module in a violation or cycle.
- Unit tests for the diagram script in `tests/`, run by the release workflow.
- Shared OutSystems 11 platform baseline (`shared/os11-platform-baseline.md`), targeting Platform Server 11.44.0, with sources. It lists the controls the platform provides, the conditions that bypass them, and what the Service Studio MCP can't see. Each audit skill carries a synced copy in `references/platform-baseline.md`.
- Every audit checks the baseline before reporting a finding, and adds an Audit Context section plus two closing sections: Platform Controls Relied On and Verify in Environment.
- Findings in all four audits carry Evidence and Confidence (Confirmed or Likely). Security findings also name the platform control considered.
- Security, performance, and maintainability audits have a Do Not Report list of common false positives.
- The maintainability audit reports every unhidden TrueChange warning as a finding.
- The report adds Platform-Provided Controls and Environment Checks sections, an audit coverage sentence, and a Likely count in the risk matrix.
- `scripts/sync_baseline.py`, run by the release workflow with `--check`, and test scenarios in `evals/scenarios.md`.

### Changed

- The Canvas diagram is easier to read: compliant references are thin and grey, violations carry a number that points to a list under the diagram instead of a text label, modules are placed to keep references straight, and the canvas widens with the number of modules.
- Side references inside Core and Foundation are reported only when they are part of a cycle.
- Module classification follows the Architecture Canvas sub-layers. There is no Orchestration layer, and Integration Services (`_IS`) are classified as Foundation instead of Core.

### Fixed

- The security audit no longer reports missing brute-force protection when logins go through the Users provider or an external identity provider. It also no longer reports generic CSRF, session fixation, SQL injection, or XSS risks that the platform already prevents.
- The performance audit no longer reports missing indexes on reference attributes whose Delete Rule is Protect or Delete, or heavy Session Variables in Reactive and Mobile apps. It now reports Advanced SQL that relies on Max Records, which doesn't limit the query.
- The maintainability audit no longer reports exception handlers as swallowing errors when Log Error is on, which is the default.

## [1.0.0] - 2026-10-14

### Added

- Five Agent Skills for auditing OutSystems 11 modules through the Service Studio MCP server: `os11-audit-architecture`, `os11-audit-security`, `os11-audit-performance`, `os11-audit-maintainability`, and `os11-audit-report`.
- Claude Code plugin (`os11-audit`) and marketplace (`agent-experience-auditor`) manifests.
- Release workflow that validates the plugin and publishes a GitHub release for each version tag.
