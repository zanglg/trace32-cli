# Contributing

Development currently targets the `dev` integration branch. Larger changes should use focused feature branches and merge into `dev` only after review and CI. `main` is reserved for tested integration/release progression.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pip install pytest ruff build
```

Or use equivalent `uv` commands.

## Validation

Run at minimum:

```bash
ruff check .
python -m pytest
python -m build
```

Changes that affect the public CLI should also preserve/update the relevant CLI smoke tests.

## Pull requests

- Target `dev` during current development.
- Keep changes focused and use a feature branch for broad refactors.
- State whether the change mutates CLI grammar, JSON/error contracts, Layer 0 backend contracts, or Layer 1 debugger semantics.
- Add/update tests for changed behavior.
- Update the applicable design/status documentation in the same change.
- Do not include proprietary target scripts, credentials, debug-unlock material, or confidential SoC information.

## Architecture changes

Read these before changing Layer 0/1 boundaries:

- [Current architecture](docs/design/ARCHITECTURE.md)
- [Layer 0/1 implementation status](docs/design/STATUS.md)

Layer 0 is the normalized TRACE32 capability adapter. Layer 1 owns deterministic debugger semantics. Layer 2/Skill owns strategy/workflow. Architecture-specific register names remain opaque until explicit semantic extensions require interpretation.

## Documentation changes

The documentation map is [docs/README.md](docs/README.md).

Keep responsibilities separate:

```text
README.md                    install/quick start/public overview
docs/design/                 current architecture + implementation status
docs/user/                   detailed user procedures
docs/maintainers/            GitHub/service administration
VERSIONING.md                version/tag/release policy
CHANGELOG.md                 release-to-release user-visible changes
AGENTS.md                    coding-Agent repository rules
```

Do not duplicate version policy in GitHub-settings documentation or duplicate the full CLI reference in prose; `t32 --json capabilities` and `t32 --json schema` are the installed-interface source of truth.

## Version and release policy

See [VERSIONING.md](VERSIONING.md). Branch workflow and semantic versioning are intentionally separate concerns.
