# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/), and each version matches a `vX.Y.Z` tag and GitHub release.

## [1.1.0] - Unreleased

### Added

- `os11-audit-architecture` now renders an Architecture Canvas diagram (SVG) of module references across the End User, Core, and Foundation layers and their sub-layers, with upward, side, and cycle violations detected and highlighted.
- `os11-audit-report` embeds the diagram in a new "Architecture Canvas Map" section.

### Changed

- Module classification follows the Architecture Canvas sub-layers. There is no Orchestration layer, and Integration Services (`_IS`) are classified as Foundation instead of Core.

## [1.0.0] - 2026-10-14

### Added

- Five Agent Skills for auditing OutSystems 11 modules through the Service Studio MCP server: `os11-audit-architecture`, `os11-audit-security`, `os11-audit-performance`, `os11-audit-maintainability`, and `os11-audit-report`.
- Claude Code plugin (`os11-audit`) and marketplace (`agent-experience-auditor`) manifests.
- Release workflow that validates the plugin and publishes a GitHub release for each version tag.
