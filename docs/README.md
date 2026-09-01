# Documentation

This directory is organized by audience and document responsibility. The goal is to keep the current system design, user procedures, and repository-maintainer policy separate so they do not drift into one another.

## Design

- [Architecture](design/ARCHITECTURE.md) — authoritative description of the current Layer 0 / Layer 1 / Layer 2 design and public routing.
- [Implementation status](design/STATUS.md) — what the generic Layer 0/1 core implements today, what still requires live TRACE32 validation, and what is intentionally deferred.

Design documents describe the current implementation. Historical alternatives and superseded implementation plans belong in Git history, issues, or pull requests rather than in the current design contract.

## User guides

- [Configuration](user/CONFIGURATION.md) — PowerView endpoint/profile configuration and setup verification.
- [Live regression testing](user/LIVE_TESTING.md) — `t32 test` plans, safety levels, and live-target regression behavior.

The root [README](../README.md) remains the primary installation and quick-start document. User guides provide detail without duplicating the full CLI reference; `t32 --json capabilities` and `t32 --json schema` are the installed-interface source of truth.

## Maintainer guides

- [GitHub repository settings](maintainers/REPOSITORY_SETTINGS.md) — GitHub UI settings that cannot be represented directly by repository files, split into initial setup and ongoing controls.
- [Release procedure](maintainers/RELEASING.md) — branch promotion, release preparation, immutable tag trigger, artifact validation, and GitHub Release automation.

Repository-level policies remain at the root where GitHub and contributors expect them:

- [Contributing](../CONTRIBUTING.md)
- [Versioning](../VERSIONING.md)
- [Security](../SECURITY.md)
- [Changelog](../CHANGELOG.md)
- [Agent development instructions](../AGENTS.md)

## Documentation ownership rules

Use these boundaries when updating documentation:

```text
README.md                 installation + quick start + public overview
docs/design/*             current architecture and implementation status
docs/user/*               detailed end-user procedures
docs/maintainers/*        repository/service/release administration
CONTRIBUTING.md            contributor workflow
VERSIONING.md              version/tag/release policy
CHANGELOG.md               release-to-release user-visible changes
AGENTS.md                  repository development rules for coding Agents
Skill                      Agent debugging strategy and runtime usage guidance
```

When implementation changes, update the applicable design/status document in the same change. Do not leave future design statements presented as already implemented behavior.
