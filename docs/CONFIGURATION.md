# Configuration

TRACE32 CLI uses layered TOML configuration so the semantic identity of a debug target can live in a repository while machine-specific PowerView endpoints remain local.

## Zero-config local PowerView

When no profile and no host are configured, `t32` connects to:

```text
localhost:20001/TCP
```

For the common local PowerView case, no configuration file is required. Verify the resolved endpoint and connectivity with:

```bash
t32 --json profile current
t32 --json doctor
```

`t32 --json profile current` reports `sources.host` as `implicit-local-default` so the fallback is explicit in machine-readable output.

A **selected profile never falls back to localhost**. If a configured/default/CLI-selected profile does not resolve a host, the CLI returns `PROFILE_HOST_MISSING`. This prevents an intended remote session from silently connecting to a local PowerView that happens to be listening on port 20001.

## Configuration sources

Persistent configuration comes from TOML files; one-off overrides come from explicit CLI options.

Highest precedence wins for each individual field:

1. explicit CLI options (`--profile`, `--host`, `--port`, `--protocol`, `--timeout`, `--packlen`)
2. `--config FILE`
3. project `config.local.toml`
4. project `config.toml`
5. user `config.toml`
6. built-in defaults
7. implicit `localhost` only if no profile/host was selected

Profile selection is `--profile`, then configured `default`.

Use explicit `--json` when machine-readable output is required.

## Files

```text
~/.config/trace32-cli/config.toml
<repo>/.trace32/config.toml
<repo>/.trace32/config.local.toml
```

On Windows, the user file uses `%APPDATA%\trace32-cli\config.toml`.

`config.local.toml` should normally be excluded from source control.

## Complete project example

The project and project-local files are one logical configuration split by ownership. Copy both files together, then change only the values relevant to the machine or target.

```toml
# <repo>/.trace32/config.toml
default = "app"

[connection]
protocol = "TCP"
timeout = 10

[profiles.app]
description = "Application processor"

[profiles.safety]
description = "Safety processor"
```

```toml
# <repo>/.trace32/config.local.toml
[profiles.app]
host = "127.0.0.1"
port = 20001

[profiles.safety]
host = "192.168.1.20"
port = 20001
```

```gitignore
# <repo>/.gitignore
.trace32/config.local.toml
```

In this example, `config.toml` is safe to share with the repository because it describes stable profile identities and common connection behavior. `config.local.toml` supplies machine-specific endpoints and stays local. A named local profile therefore uses an explicit local host, while a remote profile uses its explicit remote host.

## Remote configuration

For a one-command remote override:

```bash
t32 --host 192.168.1.20 --port 20001 --json doctor
```

For a persistent remote target, add or update the profile definition in `config.toml`, then set that profile's `host` and `port` in `config.local.toml` as shown in the complete example above.

Connection failures include the resolved endpoint, its host source, and local/remote configuration hints.

## Project configuration procedure

When configuring a project:

1. Inspect `t32 --json capabilities`, `t32 --json profile list`, and `t32 --json profile current` before editing configuration.
2. Preserve existing configuration.
3. Use zero configuration for a single local PowerView on `localhost:20001` unless a named profile or different port is required.
4. Treat `.trace32/config.toml` and `.trace32/config.local.toml` as one logical configuration pair: keep stable/shareable profile definitions in the former and machine-specific endpoints in the latter.
5. Ensure `.trace32/config.local.toml` is gitignored.
6. For remote endpoints, configure an explicit host for every named profile.
7. Use explicit CLI flags for temporary one-command overrides.
8. Verify with `t32 --json profile current` and `t32 --json doctor`.

Configuration verification ends at `doctor`. Attaching to the target, changing execution state, writing target state, mutating breakpoints, and running live self-tests are separate debugging/regression operations.
