# GitHub repository settings

This document covers GitHub settings that cannot be fully represented by files in the repository. It is a maintainer/admin guide, not a release-versioning specification.

Version numbers, release tags, prerelease rules, and tag immutability are defined in [VERSIONING.md](../../VERSIONING.md). CI behavior is defined by `.github/workflows/`. Contribution workflow is defined in [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Initial repository setup

These items are normally configured once when creating or formalizing the repository, then revisited only when project governance changes.

### Repository About metadata

Suggested description:

```text
A structured CLI for Lauterbach TRACE32 via PYRCL, with Agent Skills for AI-assisted embedded debugging.
```

Suggested topics should stay concise and relevant. A reasonable baseline is:

```text
trace32
lauterbach
pyrcl
embedded-debugging
debugger
cli
python
remote-api
agent-skills
```

Avoid using repository topics as a dumping ground for every implementation technology or transient development tool.

### Merge-method policy

Recommended baseline:

- enable squash merge
- disable merge commits when linear PR history is desired
- enable automatic deletion of merged head branches
- enable rebase merge only if maintainers intentionally support that workflow

The repository should have one documented merge policy rather than enabling every merge method by default.

### Initial branch/ruleset setup

Once CI is established and passing, configure rules for the integration/release branches appropriate to the current development workflow.

For `main`, recommended protections include:

- require pull requests before merging
- require successful CI status checks
- require conversation resolution
- block force pushes
- block branch deletion
- require linear history if the selected merge policy depends on it

Approval count is a governance choice rather than a technical requirement. A single-maintainer repository may start with zero required approvals; increase it when collaboration/review policy requires it.

During early development, `dev` may intentionally have lighter rules than `main`. Once `dev` becomes a shared integration branch, add the protections required by the actual team workflow rather than leaving it permanently unprotected by convention.

## Ongoing repository maintenance

These settings are not "done once and forgotten". Review them when the project changes maintainers, release cadence, branch strategy, or CI requirements.

### Required status checks

When CI job names or workflow structure changes, update the GitHub ruleset so the checks required by branch protection still correspond to the current workflow.

Do not duplicate the list of CI commands here; `.github/workflows/ci.yml` and `AGENTS.md` are the operational sources of truth.

### Branch policy

Keep branch protection aligned with the documented development workflow in `CONTRIBUTING.md`.

If the project later changes from `feature -> dev -> main` to another model, update together:

```text
CONTRIBUTING.md
GitHub branch rulesets
CI trigger branches
release procedure if affected
```

### Release-tag protection

When published releases are used, protect the release-tag namespace used by the project, currently:

```text
v*
```

The semantic meaning and immutability policy for those tags belong to `VERSIONING.md`. GitHub rules should enforce that policy by preventing accidental deletion or rewriting where supported.

### Repository metadata

Revisit description/topics only when the project scope materially changes. They should describe the current product, not historical bootstrap details.

## What does not belong in this document

Do not put these policies here:

```text
version numbering / SemVer        -> VERSIONING.md
release notes                     -> CHANGELOG.md
contributor branch/PR workflow    -> CONTRIBUTING.md
CI command definitions            -> .github/workflows/ci.yml + AGENTS.md
system architecture               -> docs/design/ARCHITECTURE.md
user configuration/testing        -> docs/user/
```

Keeping these responsibilities separate avoids repository settings becoming a second, stale copy of project policy.
