# TRACE32 CLI

A structured, agent-friendly CLI for Lauterbach TRACE32 via PYRCL, with a bundled `t32` Agent Skill for AI-assisted embedded debugging.

> **Status:** `0.0.0` — initial development baseline. The public interface is intentionally unstable until `1.0.0`.

## Installation and setup

These steps are intended to be followed directly by either a human or a shell-capable Agent.

### 1. Install the CLI

```bash
uv tool install git+https://github.com/zanglg/trace32-cli@dev
```

### 2. Verify the CLI

```bash
t32 --version
t32 --json capabilities
```

`capabilities` is the machine-readable entry point for the installed CLI and exposes the current configuration, discovery, safety, and self-test contracts.

### 3. Install the bundled `t32` Agent Skill

```bash
t32 skill install
t32 skill status
```

The Skill teaches a shell-capable Agent how to discover the installed CLI, configure PowerView safely, preserve evidence before mutations, and choose appropriate debugging primitives. The CLI remains fully usable without the Skill for manual or scripted use.

If an Agent cannot dynamically load a newly installed Skill in the current session, the same guidance is available with:

```bash
t32 skill show
```

### 4. Configure TRACE32

For a single local PowerView on the default endpoint, no configuration file is required:

```text
localhost:20001/TCP
```

For a named project profile, copy this baseline configuration pair and adjust the profile name, description, host, or port as needed.

```toml
# <repo>/.trace32/config.toml
default = "app"

[connection]
protocol = "TCP"
timeout = 10

[profiles.app]
description = "Application processor"
```

```toml
# <repo>/.trace32/config.local.toml
[profiles.app]
host = "127.0.0.1"
port = 20001
```

Add the machine-local file to the repository ignore rules:

```gitignore
.trace32/config.local.toml
```

The two TOML files form one configuration: `config.toml` contains the stable/shareable profile definition, while `config.local.toml` supplies the machine-specific PowerView endpoint. For a remote PowerView, change only the local `host`/`port`. A selected profile must resolve an explicit host and never falls back to the implicit local endpoint.

User-level configuration is also available at:

```text
~/.config/trace32-cli/config.toml
```

For a one-command remote override, use explicit CLI options:

```bash
t32 --host 192.168.1.20 --port 20001 --json doctor
```

Configuration precedence is:

```text
explicit CLI options
    ↓
--config FILE
    ↓
<repo>/.trace32/config.local.toml
    ↓
<repo>/.trace32/config.toml
    ↓
~/.config/trace32-cli/config.toml
    ↓
built-in defaults
    ↓
implicit localhost (only with no selected profile/host)
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full configuration reference.

### 5. Verify the setup with `doctor`

Inspect the resolved endpoint and its provenance, then verify CLI/PYRCL/PowerView connectivity:

```bash
t32 --json profile current
t32 --json doctor
```

Setup ends here. `doctor` only opens and closes the PowerView Remote API connection; it does not attach to the target or change target state. Live self-tests are a separate regression feature and are not part of installation/setup verification.

## Using TRACE32 CLI

Discover the exact installed interface instead of relying on a duplicated command reference:

```bash
t32 --json capabilities
t32 --json schema
```

Runtime target discovery:

```bash
t32 --json target info
t32 --json reg list --core 0
t32 --json bp enums
```

The CLI exposes structured resources for target state, execution control, addresses, registers, memory, symbols, variables, breakpoints, PRACTICE macros/scripts, and raw TRACE32 commands/functions.

For human help:

```bash
t32
t32 --help
t32 <resource> --help
t32 <resource> <action> --help
```

## Live regression testing

Self-tests are optional post-setup regression tools. They are not required to install, configure, or validate PowerView connectivity.

The default plan is observation-only:

```bash
t32 test
```

Optional plans are cumulative through `--execution`:

```bash
t32 test --memory
t32 test --extended
t32 test --execution
```

`--all` runs every registered self-test suite:

```bash
t32 test --all
```

| Plan | Adds | Important side effects |
| --- | --- | --- |
| `t32 test` | runtime/target/register/breakpoint reads and `P:<PC>` memory reads | observation only |
| `--memory` | TRACE32 `VM:` raw/typed/endian round-trips | writes only TRACE32 VM scratch and restores it |
| `--extended` | temporary breakpoint lifecycle | debugger/breakpoint state changes; implementation is runtime-dependent |
| `--execution` | Break/Step/Go | executes target instructions; side effects cannot be undone |
| `--all` | every registered suite | highest current/future risk |

`VM:` is TRACE32's virtual-memory access class, not target `D:`/`P:` memory and not the target CPU's MMU virtual address space.

For machine-readable reports:

```bash
t32 --json test --all
```

See [docs/TESTING.md](docs/TESTING.md) for exact safety semantics.

## Architecture

```text
TRACE32 PowerView
      ↑
  RCL / PYRCL
      ↑
  t32 CLI primitives
      ↑
  Agent / t32 Skill
```

The CLI remains architecture-neutral. Runtime facts come from `target info`, `reg list`, and PYRCL rather than a hard-coded CPU/register catalog.

## Development

Current development happens on `dev`. `main` remains the bootstrap branch until the initialization baseline is ready to promote.

See [VERSIONING.md](VERSIONING.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [docs/CONFIGURATION.md](docs/CONFIGURATION.md), and [docs/TESTING.md](docs/TESTING.md).

TRACE32 is a product/trademark of Lauterbach. This is an independent community project and is not affiliated with or endorsed by Lauterbach GmbH.
