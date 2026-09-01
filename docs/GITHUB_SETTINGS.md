# Recommended GitHub repository settings

Some settings cannot be expressed as repository files and must be applied in GitHub Settings.

## About

Description:

```text
A structured CLI for Lauterbach TRACE32 via PYRCL, with Agent Skills for AI-assisted embedded debugging.
```

Recommended topics:

```text
trace32
lauterbach
pyrcl
embedded-debugging
debugger
cli
ai-agent
agent-skills
codex
pi
jtag
firmware
python
remote-api
```

## Merge settings

Recommended after development workflow is established:

- Enable squash merge.
- Disable merge commits.
- Disable rebase merge if a strict one-PR/one-commit history is desired.
- Automatically delete head branches after merge.

## `main` ruleset

Recommended once CI has completed successfully at least once:

- Target: `main`.
- Require pull requests before merging.
- Initially require 0 approvals for a single-maintainer repository; increase to 1 when collaborators join.
- Require conversation resolution.
- Require status checks from CI.
- Require linear history.
- Block force pushes.
- Block branch deletion.

Do not protect `dev` as strictly during the initial cross-environment test cycle unless needed.

## Release tag ruleset

When releases begin, protect tags matching:

```text
v*
```

Prevent deletion or rewriting of release tags. Release tags must follow SemVer as documented in `VERSIONING.md`.

## Current initialization policy

No `v0.0.0` tag and no GitHub Release should be created until the `dev` baseline passes cross-environment testing.
