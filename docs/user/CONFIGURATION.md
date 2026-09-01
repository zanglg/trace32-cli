# Configuration

TRACE32 CLI keeps persistent configuration intentionally small: one user-level file and one project-level file. Temporary overrides stay on the command line instead of creating additional persistent overlay files.

## Configuration model

Persistent precedence, highest first:

1. project `.trace32/config.toml`
2. user `~/.config/trace32-cli/config.toml`
3. built-in defaults

Above persistent configuration, one-command overrides apply in this order:

1. explicit CLI options (`--profile`, `--host`, `--port`, `--protocol`, `--timeout`, `--packlen`)
2. `--config FILE`

The effective conceptual order is therefore:

```text
CLI options
    ↓
--config FILE
    ↓
<project>/.trace32/config.toml
    ↓
~/.config/trace32-cli/config.toml
    ↓
built-in defaults
    ↓
implicit localhost only when no profile/host is selected
```

There is no `config.local.toml` layer. If a machine needs a one-off endpoint that should not be committed to a project file, use CLI options or `--config FILE`.

## Files

```text
~/.config/trace32-cli/config.toml
<project>/.trace32/config.toml
```

On Windows, the user file uses:

```text
%APPDATA%\trace32-cli\config.toml
```

## Project discovery

`t32` starts from the current working directory and walks upward until it finds the nearest:

```text
.trace32/config.toml
```

That directory becomes the TRACE32 project root.

This is intentionally independent of the Git top-level. For example:

```text
repo/
├── .git/
├── product-a/
│   ├── .trace32/
│   │   └── config.toml
│   └── firmware/
└── product-b/
```

Running `t32` from `repo/product-a/firmware` resolves `repo/product-a/.trace32/config.toml`, not `repo/.trace32/config.toml`.

If no project `.trace32/config.toml` is found in the ancestor chain, the Git top-level is used only as the candidate project root for reporting/config-location discovery; if no config exists there, user config and defaults remain active.

## Bare `t32` configuration summary

Running:

```bash
t32
```

is read-only and does not connect to PowerView. It resolves configuration and shows:

```text
project root
profile
endpoint
config files used
```

This is the quickest way to verify that a project `.trace32/config.toml` is being detected.

For machine-readable details use:

```bash
t32 --json profile current
```

## Zero-config local PowerView

When no profile and no host are configured, `t32` uses:

```text
localhost:20001/TCP
```

No configuration file is required for that common case.

`t32 --json profile current` reports `sources.host` as `implicit-local-default`, making the fallback explicit in machine-readable output.

A selected profile never falls back to localhost. If a configured/default/CLI-selected profile does not resolve a host, the CLI returns `PROFILE_HOST_MISSING`.

## User-level defaults

Use the user file for defaults that apply broadly on one workstation. Example:

```toml
# ~/.config/trace32-cli/config.toml
[connection]
protocol = "TCP"
timeout = 10
```

You can also define reusable profiles there:

```toml
[profiles.lab]
description = "Lab PowerView"
host = "192.168.1.20"
port = 20001
```

## Project configuration

A project can override user defaults and define its normal target endpoint directly:

```toml
# <project>/.trace32/config.toml
default = "app"

[connection]
protocol = "TCP"
timeout = 10

[profiles.app]
description = "Application processor"
host = "127.0.0.1"
port = 20001

[profiles.safety]
description = "Safety processor"
host = "192.168.1.20"
port = 20001
```

For the usual local TRACE32 setup, committing `127.0.0.1:20001` in the project profile is acceptable when that endpoint is genuinely part of the project's expected development setup.

## Temporary overrides

For a one-command remote endpoint:

```bash
t32 --host 192.168.1.20 --port 20001 --json doctor
```

To select a different configured profile:

```bash
t32 --profile safety --json doctor
```

To apply a temporary TOML file above user/project configuration:

```bash
t32 --config /tmp/trace32-test.toml --json profile current
```

`--config FILE` is useful for machine-specific or experimental settings that should not be committed to the project.

## Profile resolution

Profile selection is:

```text
--profile
    ↓
configured default
```

After selecting a profile, fields are resolved through the normal user → project → explicit config → CLI precedence.

A named profile must resolve an explicit `host`.

## Verification procedure

When configuring a project:

1. Run bare `t32` and verify that the expected project root/config file is shown.
2. Inspect `t32 --json capabilities`, `t32 --json profile list`, and `t32 --json profile current`.
3. Keep workstation-wide defaults in the user config.
4. Keep normal project-specific profiles/endpoints in `.trace32/config.toml`.
5. Use CLI flags or `--config FILE` for temporary machine-specific overrides.
6. For remote endpoints, configure an explicit host for every named profile.
7. Verify PowerView connectivity with `t32 --json doctor`.

Configuration verification ends at `doctor`. Attaching to the target, changing execution state, writing target state, mutating breakpoints, and running live self-tests are separate debugging/regression operations.
