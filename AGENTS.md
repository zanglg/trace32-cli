# AGENTS.md — Development instructions

This file governs development of `trace32-cli`; it is not the end-user debugging Skill.

## Architecture

Keep the project as a thin structured adapter over documented PYRCL primitives:

```text
TRACE32 / PYRCL
      ↑
trace32_cli.cli       stable primitive handlers + base grammar
      ↑
trace32_cli.runtime   runtime capability discovery only
trace32_cli.selftest  self-test plans/runners only
trace32_cli.config    layered endpoint/profile resolution
      ↑
trace32_cli.app       public assembly, diagnostics, output contract
      ↑
trace32_cli.entry     minimal `t32` console entry
```

Rules:

- Keep architecture-specific debugging strategy out of primitives.
- Preserve `t32 RESOURCE ACTION ...` grammar and structured JSON envelopes.
- Prefer typed/documented PYRCL services over raw commands.
- Keep `raw cmd` and `raw fnc` explicit escape hatches.
- Do not implement the same primitive in both `cli.py` and `runtime.py`.
- Keep self-test plan policy in `selftest.py`, not parser/bootstrap code.
- Comments should explain non-obvious safety/API constraints, not narrate obvious code.
- Do not add daemon/MCP complexity without a separate design decision.

## User-facing documentation

- Describe the current public contract, not discarded development iterations.
- Keep the primary setup sequence explicit: install CLI → verify CLI → install Skill → configure TRACE32 → verify with `profile current` and `doctor`.
- `doctor` is the setup/configuration/connectivity verification boundary. Do not present `t32 test` as an installation requirement.
- Treat the README setup section as the canonical instructions for both humans and shell-capable Agents; do not maintain a duplicate setup prompt that can drift from it.
- Prefer complete, copyable configuration examples that show the project and project-local files together while preserving their ownership boundary.

## Changelog policy

`CHANGELOG.md` records release-to-release user-visible net changes. Do not narrate implementation experiments or reversals that happened entirely within the same unreleased version. Development history belongs in commits, issues, and pull requests.

For the first public release, the Unreleased section should read like a coherent release-note draft for the final shipped contract rather than a timeline of bootstrap iterations.

## Versioning

The current initialization version is `0.0.0`. Release tags use `vMAJOR.MINOR.PATCH`.

## Bundled end-user Skill

The Skill source is:

```text
trace32_cli/skills/t32/
```

Users install it with `t32 skill install`. The Skill should teach discovery, configuration, safety, and debugging discipline rather than duplicate the entire CLI reference.

## Before completing a change

Run at minimum:

```bash
python -m pytest
ruff check .
python -m build
```

Smoke-test:

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
```
