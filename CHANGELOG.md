# Changelog

All notable changes to this project will be documented here.

The project follows Semantic Versioning. This changelog records release-to-release user-visible net changes; development-only iterations within an unreleased version are intentionally omitted.

## [Unreleased]

### Added

- Structured `t32` CLI for Lauterbach TRACE32 automation over PYRCL, with typed target, execution, address, register, memory, symbol, variable, breakpoint, PRACTICE, and raw command/function primitives.
- Structured JSON success/error envelopes, stable exit-code categories, machine-readable `capabilities`, and exact installed-command `schema` discovery.
- Runtime target discovery through `target info`, register enumeration, and breakpoint enum discovery.
- Layered TOML configuration for user, project, and project-local settings, including zero-config local `localhost:20001` behavior, named PowerView profiles, explicit one-command overrides, provenance reporting, and guarded remote-profile resolution.
- Read-only `doctor` diagnostics for CLI, PYRCL, resolved configuration, and PowerView Remote API connectivity.
- Bundled `t32` Agent Skill with install/status/show/uninstall commands and guidance for configuration, discovery, safety, and Agent-assisted embedded debugging.
- Live regression plans with observation-only `t32 test`, TRACE32 `VM:` memory round-trips via `--memory`, temporary debugger/breakpoint-state coverage via `--extended`, execution-control coverage via `--execution`, and future-facing full-suite selection via `--all`.
- Repository CI across supported Python versions, packaging checks, contribution/security/versioning guidance, and Agent development instructions.
