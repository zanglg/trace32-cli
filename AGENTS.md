# AGENTS.md — Development instructions

This file governs development of `trace32-cli`; it is not the end-user debugging Skill.

## Architecture

Keep the project layered so TRACE32 mechanisms, debugger semantics, and Agent workflows do not collapse into one abstraction:

```text
TRACE32 / PYRCL
      ↑
trace32_cli.layer0          TRACE32 capability adapters, runtime capabilities, stable backend errors
      ↑
trace32_cli.layer1          generic debugger semantics + CLI handlers
      ↑
trace32_cli.completed_app   current public debugger command assembly
      ↑
trace32_cli.layered_app     lower layered assembly reused by completed_app
trace32_cli.app             configuration, diagnostics, discovery compatibility shell
trace32_cli.cli             legacy grammar/helpers and compatibility primitives
trace32_cli.runtime         runtime target-discovery compatibility helpers
trace32_cli.selftest        self-test plans/runners only
trace32_cli.config          endpoint/profile resolution
      ↑
trace32_cli.entry           minimal `t32` console entry

trace32_cli/skills/t32      Layer 2 Agent strategy/workflow guidance
```

Rules:

- Layer 0 stays a thin normalized adapter over documented PYRCL/TRACE32 primitives.
- Layer 0 owns backend capability negotiation, parameter normalization, backend syntax adaptation, and backend-specific error normalization.
- Layer 1 models GDB-inspired debugger semantics, not GDB CLI syntax.
- New generic debugger behavior belongs in Layer 1; do not add direct PYRCL service calls to public CLI handlers.
- Keep architecture-specific debugging strategy out of Layer 0 and generic Layer 1 primitives.
- Treat architecture-specific register names as opaque strings until semantic interpretation is explicitly required.
- Preserve `t32 RESOURCE ACTION ...` grammar and structured JSON envelopes unless a deliberate public-interface change is approved.
- Prefer documented PYRCL services over raw TRACE32 commands when they represent the same capability.
- Keep `raw cmd`, `raw fnc`, PRACTICE/CMM, and direct access explicit Layer 0 escape hatches.
- Use CMM for TRACE32-specific workflows/bring-up, not as the default implementation of generic register/memory/execution primitives.
- Stop-reason classification must be evidence-based. Preserve `unknown` rather than guessing exception/watchpoint/exit causes.
- Generic task context may use TRACE32 OS-awareness TASK/Frame semantics; do not hard-code one RTOS model into Layer 1.
- Keep self-test plan policy in `selftest.py`, not parser/bootstrap code.
- Comments should explain non-obvious safety/API constraints, not narrate obvious code.
- Do not add daemon/MCP complexity without a separate design decision.

The authoritative current architecture is `docs/design/ARCHITECTURE.md`. The current implementation/validation boundary is `docs/design/STATUS.md`. Update those documents in the same change when their statements cease to match the code.

## Public implementation source of truth

The console entry is `trace32_cli.entry`, currently routed to `trace32_cli.completed_app`. `completed_app` extends `layered_app`; do not describe `layered_app` alone as the current public entry.

Machine-readable public command truth is:

```bash
t32 --json capabilities
t32 --json schema
```

Connected backend/runtime discovery is:

```bash
t32 --json backend capabilities
t32 --json target info
t32 --json bp enums
```

## Configuration contract

Persistent configuration has exactly two levels:

```text
~/.config/trace32-cli/config.toml
<project>/.trace32/config.toml
```

Project config overrides user config. Project discovery walks upward from the current working directory to the nearest `.trace32/config.toml`; do not assume Git top-level is the project root.

Use CLI options or `--config FILE` for temporary/machine-specific overrides. Do not reintroduce a `config.local.toml` layer without a separate design decision.

Bare `t32` must remain read-only and should display the resolved project root/profile/endpoint/config files so configuration discovery is visible without connecting to PowerView.

## Documentation structure

Use `docs/README.md` as the documentation map.

```text
README.md                    install + quick start + public overview
docs/design/ARCHITECTURE.md current architecture
docs/design/STATUS.md       implementation/validation boundary
docs/user/                  detailed end-user procedures
docs/maintainers/           repository/service administration
CONTRIBUTING.md             contributor workflow
VERSIONING.md               version/tag/release policy
CHANGELOG.md                release-to-release user-visible changes
AGENTS.md                   coding-Agent repository rules
Skill                       Agent debugging strategy/runtime guidance
```

Documentation rules:

- Describe the current implementation, not planned or discarded iterations.
- When a feature is runtime-dependent, distinguish software/API validation from real TRACE32 target validation.
- Do not claim architecture-specific exception/MMU/privilege/CSA semantics exist until they are implemented.
- Keep the primary setup sequence explicit: install CLI → verify CLI → install Skill → configure TRACE32 → verify with `profile current` and `doctor`.
- `doctor` is the setup/configuration/connectivity verification boundary. Do not present `t32 test` as an installation requirement.
- README is the quick-start/public overview, not a duplicate of the full architecture/status documents.
- `VERSIONING.md` is the single source of truth for SemVer/tag/release policy; do not redefine those rules in GitHub-settings docs.
- `docs/maintainers/REPOSITORY_SETTINGS.md` only describes GitHub settings that cannot be represented directly by repository files and how they enforce other repository policies.
- Keep README, design/status docs, bundled Skill, `capabilities`, and `schema` mutually consistent.
- Configuration examples must use the two-level user/project model and temporary CLI/`--config` overrides.

## Changelog policy

`CHANGELOG.md` records release-to-release user-visible net changes. Do not narrate implementation experiments or reversals that happened entirely within the same unreleased version. Development history belongs in commits, issues, and pull requests.

For the first public release, the Unreleased section should read like a coherent release-note draft for the final shipped contract rather than a timeline of bootstrap iterations.

## Versioning

The current initialization version is `0.0.0`. Version/tag/release rules are defined only in `VERSIONING.md`.

## Bundled end-user Skill

The Skill source is:

```text
trace32_cli/skills/t32/
```

Users install it with `t32 skill install`. The Skill should teach discovery, configuration, safety, stop-reason confidence, runtime capability handling, and debugging strategy rather than duplicate the entire CLI reference.

## Before completing a change

Run at minimum:

```bash
python -m pytest
ruff check .
python -m build
```

Smoke-test local/discovery/help surfaces that do not require PowerView:

```bash
t32
t32 --help
t32 --json about
t32 --json capabilities
t32 --json schema
t32 test --help
t32 skill --help
t32 reg read --help
t32 mem read --help
t32 exec --help
t32 source --help
t32 stack --help
t32 backend --help
t32 context --help
t32 frame --help
t32 practice run --help
```

Runtime commands such as `backend capabilities`, target access, OS-awareness task enumeration, source/disassembly, and execution semantics require a suitable PowerView/target configuration and must not be represented as hardware-validated solely because software CI passes.
