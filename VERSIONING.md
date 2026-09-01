# Versioning and releases

`trace32-cli` follows [Semantic Versioning 2.0.0](https://semver.org/).

This file is the authoritative policy for package versions, release tags, prereleases, and release immutability. GitHub repository settings should enforce this policy where possible but must not redefine it.

## Version format

Package versions use:

```text
MAJOR.MINOR.PATCH
```

Release tags use:

```text
vMAJOR.MINOR.PATCH
```

Prerelease examples:

```text
0.1.0-alpha.1
0.1.0-beta.1
0.1.0-rc.1
```

with corresponding tags such as `v0.1.0-rc.1`.

## Initial-development policy

- `0.0.0` is the repository/bootstrap development version and is not itself a public compatibility commitment.
- `0.x.y` means the public interface is still evolving; breaking changes may occur between minor versions.
- `1.0.0` means the supported CLI grammar, JSON/error contract, exit-code contract, and Skill installation interface have a defined compatibility policy.

Even during `0.x`, avoid unnecessary breaking changes and record intentional user-visible incompatibilities in `CHANGELOG.md`.

## What constitutes a release

A published release consists of one immutable source commit identified by a version tag. Package metadata, changelog entry, and release notes must describe that same version.

Before creating a release tag:

1. choose the release version according to SemVer;
2. update package/version metadata as required by the repository;
3. finalize the corresponding `CHANGELOG.md` section;
4. run required repository CI/validation;
5. ensure the release commit is the exact content intended to publish;
6. create the version tag once and do not move it later.

Live TRACE32 validation requirements may differ by release maturity. The current implementation/validation boundary is documented in `docs/design/STATUS.md`; release decisions should state whether a version is software-CI validated only or has representative live-target validation.

## Tag policy

Published release tags are immutable.

Never:

- move an existing release tag to another commit;
- delete and recreate a published release tag to change its content;
- reuse an existing version number for different source content.

If a published release is wrong, fix it in a new version according to SemVer.

GitHub repository settings should protect the `v*` namespace from accidental deletion or rewriting where supported; see `docs/maintainers/REPOSITORY_SETTINGS.md`.

## Prereleases

Use prerelease identifiers when the package is intentionally distributed for validation before a stable release, for example:

```text
0.1.0-alpha.1   early implementation/integration validation
0.1.0-beta.1    broader compatibility validation
0.1.0-rc.1      release-candidate validation
```

Do not use prerelease tags merely as disposable CI checkpoints; ordinary feature branches and pull requests already serve that purpose.

## Changelog relationship

`CHANGELOG.md` records release-to-release user-visible net changes. Development experiments that are added and removed before a release do not need separate release-note entries.

When releasing, move/finalize the relevant Unreleased content into the released version section using the version and release date.

## Branches are not versions

Branches such as `dev`, `main`, and `feat/*` describe development workflow, not semantic versions. Branch policy belongs in `CONTRIBUTING.md` and GitHub repository rules, not in version numbering.
