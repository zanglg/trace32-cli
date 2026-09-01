# Contributing

Development uses two long-lived branches:

- `dev` is the next-version integration branch.
- `main` contains released or release-ready history.

Feature branches are short-lived. Merge feature branches into `dev` with **squash merge**, then delete the feature branch. Promote a release-ready `dev` to `main` with **fast-forward only** so `main` preserves the curated feature-level history without merge commits or release-only squash commits.

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

- Target `dev` for feature and bug-fix development.
- Keep changes focused and use a short-lived feature branch for non-trivial work.
- Squash feature branches into `dev` after review and required CI pass.
- Delete feature branches after they are integrated.
- State whether the change mutates CLI grammar, JSON/error contracts, Layer 0 backend contracts, or Layer 1 debugger semantics.
- Add/update tests for changed behavior.
- Update the applicable design/status documentation in the same change.
- Do not include proprietary target scripts, credentials, debug-unlock material, or confidential SoC information.

## Release progression

A release-ready `dev` is promoted to `main` by fast-forward only. Do not squash `dev` into a synthetic release commit and do not create merge commits between `dev` and `main`.

Published `vMAJOR.MINOR.PATCH` tags must point to commits contained in `main` and are immutable. Pushing a valid release tag triggers the repository release workflow, which validates the tag/package version, builds and smoke-tests the wheel, and creates the GitHub Release. See [Release procedure](docs/maintainers/RELEASING.md) and [Versioning](VERSIONING.md).

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
docs/maintainers/            repository/release administration
VERSIONING.md                version/tag/release policy
CHANGELOG.md                 release-to-release user-visible changes
AGENTS.md                    coding-Agent repository rules
```

Do not duplicate version policy in GitHub-settings documentation or duplicate the full CLI reference in prose; `t32 --json capabilities` and `t32 --json schema` are the installed-interface source of truth.
