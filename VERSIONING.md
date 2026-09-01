# Versioning

`trace32-cli` follows [Semantic Versioning 2.0.0](https://semver.org/).

## Format

Package versions use:

```text
MAJOR.MINOR.PATCH
```

Git release tags use:

```text
vMAJOR.MINOR.PATCH
```

Valid prerelease examples:

```text
0.1.0-alpha.1
0.1.0-beta.1
0.1.0-rc.1
```

Corresponding tags are `v0.1.0-alpha.1`, etc.

## Initial-development policy

- `0.0.0`: repository bootstrap / initialization baseline.
- `0.x.y`: public interface is unstable and may change between minor releases.
- `1.0.0`: CLI grammar, JSON contract, exit-code contract, and Skill installation interface are considered stable.

Even during `0.x`, avoid unnecessary breaking changes and document intentional incompatibilities in `CHANGELOG.md`.

## Tag policy

Release tags are immutable. Never move, replace, or recreate a published release tag to point at different content.

No release tag is created for `0.0.0` until the initialization baseline has passed cross-environment testing.
