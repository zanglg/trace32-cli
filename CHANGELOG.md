# Changelog

All notable changes to this project will be documented here.

The project follows Semantic Versioning. This changelog records release-to-release user-visible net changes; development-only iterations within an unreleased version are intentionally omitted.

## [Unreleased]

## [0.1.0] - 2026-09-01

### Added

- Structured `t32` CLI for Lauterbach TRACE32 automation over PYRCL, with layered target, execution, context, address, register, memory, symbol, variable/expression/type, breakpoint/watchpoint, source/location, instruction/disassembly, stack/frame, program/image, PRACTICE, and raw command/function capabilities.
- Layer 0 TRACE32 capability adapter modeled after PYRCL structured services and explicit command/function/PRACTICE/direct-access escape hatches.
- Runtime Layer 0 capability negotiation through `backend capabilities`, including service/feature availability and normalized breakpoint parameter discovery.
- Stable Layer 0 backend error taxonomy for connection, timeout, address, register, memory, breakpoint, symbol, variable, PRACTICE, unsupported-operation, raw command/function, and generic backend failures.
- PRACTICE/CMM positional arguments and timeout control, including non-blocking `--timeout 0` behavior, routed through Layer 0.
- Layer 1 GDB-inspired generic debugger semantics, including instruction/source stepping, step-over, finish, run-to, wait/stop events, unified locations, memory search/compare/fill, watchpoints, source/disassembly, stack/frame navigation, and image/symbol loading.
- Conservative stop-reason results with reason source/confidence metadata and exact program-breakpoint PC inference instead of guessing unsupported stop causes.
- Generic TRACE32 OS-awareness task context with current/list/select operations plus selected-frame current/select semantics.
- Structured expression/type results with value/type/address/size metadata, structured location resolution, and disassembly results enriched with available source/symbol information.
- Architecture-neutral register handling: architecture-specific names such as `TTBR0_EL1`, `ESR_EL1`, `mstatus`, and `mcause` remain opaque parameters rather than a hard-coded register database.
- Structured JSON success/error envelopes, stable exit-code categories, machine-readable `capabilities`, and exact installed-command `schema` discovery.
- Runtime target discovery through `target info`, register enumeration, execution/context discovery, and breakpoint parameter discovery.
- Two-level persistent TOML configuration (user + nearest project `.trace32/config.toml`), with upward project discovery independent of Git top-level, explicit one-command overrides, provenance reporting, guarded remote-profile resolution, and read-only bare `t32` resolved-configuration output.
- Read-only `doctor` diagnostics for CLI, PYRCL, resolved configuration, and PowerView Remote API connectivity.
- Bundled `t32` Agent Skill with install/status/show/uninstall commands and guidance for configuration, discovery, safety, backend capabilities, stop-reason confidence, layered debugger use, and Agent-assisted embedded debugging.
- Live regression plans with observation-only `t32 test`, Layer 1 → Layer 0 TRACE32 host-side `VM:` memory round-trips via `--memory` using an automatically initialized dedicated 256-byte scratch range, temporary debugger/breakpoint-state coverage via `--extended`, execution-control coverage via `--execution`, and future-facing full-suite selection via `--all`.
- Repository CI across supported Python versions, packaging checks, contribution/security/versioning guidance, Agent development instructions, and tag-triggered GitHub Release automation with built-wheel smoke validation.
