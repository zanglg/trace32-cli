# Release procedure

This runbook describes how maintainers promote a release-ready `dev` to an immutable GitHub release. Semantic version and tag policy is authoritative in [`VERSIONING.md`](../../VERSIONING.md).

## Branch model

```text
feature/* --squash--> dev --fast-forward--> main --tag--> GitHub Release
```

- `dev` is the next-version integration branch.
- `main` contains released or release-ready history.
- Feature branches are short-lived and deleted after squash integration into `dev`.
- `dev` must be promoted to `main` by fast-forward only; do not squash the whole release into one commit and do not create a merge commit between `dev` and `main`.

## Prepare the release on `dev`

Before promotion:

1. choose the version according to `VERSIONING.md`;
2. update `pyproject.toml` to the release version;
3. finalize the dated version section in `CHANGELOG.md` and leave a fresh `Unreleased` section;
4. update README/status documentation when release maturity or validation evidence changed;
5. run repository CI successfully;
6. for changes that require TRACE32 validation, record the representative live-validation boundary in `docs/design/STATUS.md`;
7. ensure the exact `dev` tree is the content intended to release.

For `0.1.0`, representative live PowerView + physical-target validation passed every currently registered `t32 test --all` case. This does not imply exhaustive compatibility across all targets, PowerView versions, OS-awareness configurations, or optional services.

## Promote to `main`

Verify `main` is an ancestor of `dev`, then fast-forward `main` to the exact release-ready `dev` commit. No source changes should be introduced only on `main`.

After promotion, `main` and `dev` should point to the same release commit until new development begins on `dev`.

## Trigger the release

Create the immutable version tag on the release commit in `main`:

```bash
git tag vMAJOR.MINOR.PATCH
git push origin vMAJOR.MINOR.PATCH
```

Pushing the tag is the explicit release trigger. `.github/workflows/release.yml` then:

1. validates SemVer syntax;
2. validates tag version against package metadata;
3. verifies the tagged commit is contained in `main`;
4. builds wheel and source distribution;
5. installs and smoke-tests the built wheel in a clean virtual environment;
6. extracts the matching `CHANGELOG.md` section;
7. creates the GitHub Release and attaches the built artifacts.

Do not manually upload replacement artifacts for the same immutable release tag.

## Distribution scope

The `0.1.0` release is distributed through GitHub Releases and Git tags. PyPI publishing is intentionally not part of this release path and is not a release blocker.

Users can install a tagged release with:

```bash
uv tool install git+https://github.com/zanglg/trace32-cli@vMAJOR.MINOR.PATCH
```

PyPI may be added later as an additional distribution channel through a separate repository decision and Trusted Publishing configuration.

## After release

- Keep the published `v*` tag immutable.
- Delete integrated short-lived feature branches.
- Keep `main` at the released commit until the next promotion.
- Continue new work from `dev` using short-lived feature branches.
- If a published release is defective, fix it in a new SemVer version; never move or recreate the published tag.
