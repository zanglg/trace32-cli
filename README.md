# TRACE32 CLI

A structured, agent-friendly CLI for Lauterbach TRACE32 via PYRCL, with a bundled `t32` Agent Skill for AI-assisted embedded debugging.

> **Status:** `0.1.0` — first public alpha release. The public interface may evolve during `0.x`; compatibility policy is defined for `1.0.0`.

## Installation and setup

### 1. Install the CLI

```bash
uv tool install git+https://github.com/zanglg/trace32-cli@v0.1.0
```

For development builds, install from `dev` explicitly.

### 2. Verify the CLI

```bash
t32 --version
t32
```

Bare `t32` is read-only. It discovers the nearest project `.trace32/config.toml`, resolves the effective profile/endpoint, and shows the configuration files it used without connecting to PowerView.

For machine-readable discovery:

```bash
t32 --json capabilities
t32 --json schema
```

### 3. Install the bundled Agent Skill

```bash
t32 skill install
t32 skill status
```

The Skill teaches discovery, safety, configuration, and debugging workflow policy. The CLI remains usable without it.

### 4. Configure TRACE32

With no selected profile or explicit host, the default endpoint is:

```text
localhost:20001/TCP
```

Persistent configuration has two levels:

```text
~/.config/trace32-cli/config.toml   user defaults
<project>/.trace32/config.toml      project settings
```

The project file overrides user configuration. `t32` discovers the nearest `.trace32/config.toml` by walking upward from the current working directory, so it also works for subprojects and monorepos.

For a named project profile:

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
```

For temporary overrides, use `--profile`, `--host`, `--port`, or `--config FILE` rather than adding another persistent overlay file.

For details, see [Configuration](docs/user/CONFIGURATION.md).

### 5. Verify setup

```bash
t32 --json profile current
t32 --json doctor
```

Setup verification ends at `doctor`. It verifies configuration and PowerView Remote API connectivity without attaching to or mutating the target.

## Discover the installed contract

The installed executable is the command/API source of truth:

```bash
t32 --json capabilities
t32 --json schema
```

After connection, inspect backend/runtime capabilities:

```bash
t32 --json backend capabilities
t32 --json target info
t32 --json exec state
t32 --json context current
t32 --json reg list --core 0
t32 --json bp enums
```

When TRACE32 OS-awareness is configured:

```bash
t32 --json context task-current
t32 --json context task-list
```

Unsupported runtime capabilities return `UNSUPPORTED_OPERATION`; the CLI does not assume a particular RTOS or processor feature set.

## Generic debugger interface

The structured CLI covers target lifecycle, execution, context, registers, memory, breakpoints/watchpoints, symbols, variables/expressions/types, source locations, disassembly, stack/frame navigation, and program/image operations.

Examples:

```bash
t32 --json reg read PC SP
t32 --json reg read TTBR0_EL1
t32 --json mem read 0x1000 --type u32
t32 --json bp add main --kind symbol
t32 --json watch add 0x2000 --access write
t32 --json source current
t32 --json source resolve main --kind symbol
t32 --json insn current
t32 --json stack backtrace
t32 --json frame current
t32 --json frame select 2
t32 --json expr eval 'task->state'
t32 --json type describe 'task->state'
t32 --json exec next
t32 --json exec run-to main --kind symbol
t32 --json exec wait --timeout 5
```

Architecture-specific register names such as `TTBR0_EL1`, `ESR_EL1`, `mstatus`, and `mcause` remain opaque register-name parameters. The generic core does not maintain architecture register databases or architecture-specific exception/MMU/privilege decoders.

## Execution stop events

```bash
t32 --json exec stop-reason
```

Stop-event classification is intentionally conservative:

- CLI-initiated halt/step operations have known operation reasons;
- an exact stopped-PC match to an enabled PROGRAM breakpoint may be inferred as a breakpoint stop;
- other externally triggered stops remain `unknown` when backend evidence is insufficient.

Returned events include reason source/confidence so consumers can distinguish known facts from inference.

## Structured expressions, locations, frames, and tasks

Expression evaluation can return available value/type/address/size metadata. Location resolution can return address, symbol, and source metadata. Disassembly adds available source/symbol context.

Frame levels are zero-based from the innermost frame:

```bash
t32 --json frame current
t32 --json frame select 2
t32 frame up
t32 frame down
```

Generic OS-awareness task context is available when TRACE32 provides TASK awareness:

```bash
t32 --json context task-current
t32 --json context task-list
t32 --json context task-select worker
```

Task selection changes debugger inspection context; it does not schedule the target task.

## PRACTICE and raw TRACE32 escape hatches

Structured Layer 1 commands are preferred. TRACE32-specific workflows can use explicit Layer 0 escape hatches:

```bash
t32 practice run init.cmm cpu0 fast
t32 practice run init.cmm cpu0 --timeout 10
t32 practice run init.cmm --timeout 0

t32 raw fnc 'STATE.RUN()'
t32 raw cmd 'Break'
```

The default PRACTICE execution waits indefinitely. `--timeout 0` starts the script without polling for completion.

## Stable backend errors

Layer 0 normalizes backend-specific failures before they reach the public CLI. Stable categories include:

```text
NOT_CONNECTED
TIMEOUT
INVALID_ADDRESS
REGISTER_NOT_FOUND
REGISTER_ERROR
MEMORY_ACCESS_ERROR
BREAKPOINT_NOT_FOUND
BREAKPOINT_ERROR
SYMBOL_NOT_FOUND
VARIABLE_ERROR
PRACTICE_ERROR
UNSUPPORTED_OPERATION
TRACE32_COMMAND_ERROR
TRACE32_FUNCTION_ERROR
BACKEND_ERROR
```

Machine consumers should use JSON error codes/details instead of parsing PYRCL exception text.

## Live regression testing

Self-tests are optional post-setup regression tools:

```bash
t32 test              # observation only
t32 test --memory     # initialize/test 256-byte host-side TRACE32 VM: scratch
t32 test --extended   # temporary breakpoint lifecycle
t32 test --execution  # Break/Step/Go
t32 test --all        # every registered suite; highest risk
```

The memory suite uses the current Layer 1 → Layer 0 memory path and does not write target RAM. Its dedicated `VM:` scratch range is initialized automatically because TRACE32 VM locations may initially be uninitialized.

See [Live regression testing](docs/user/LIVE_TESTING.md) for exact safety semantics.

## Architecture and implementation status

```text
Layer 2  Agent Skill / workflow policy
              ↑
Layer 1  Generic debugger semantics
              ↑
Layer 0  Normalized TRACE32 capability adapter
              ↑
         PYRCL / TRACE32 PowerView
```

The current public route is:

```text
trace32_cli.entry
    → trace32_cli.completed_app
    → Layer 1 handlers / Debugger
    → Layer 0 PyrclBackend
    → PYRCL / PowerView
```

Authoritative design and completion boundaries are documented in:

- [Architecture](docs/design/ARCHITECTURE.md)
- [Layer 0 / Layer 1 implementation status](docs/design/STATUS.md)

Software CI validates Python 3.9–3.13, lint, unit tests, CLI smoke tests, and package build. The `0.1.0` candidate also passed every registered `t32 test --all` case against a real TRACE32 PowerView session and physical target; broader cross-target/runtime validation remains ongoing.

## Documentation

Start with [docs/README.md](docs/README.md) for the documentation map.

Repository policy documents remain at the root:

- [Contributing](CONTRIBUTING.md)
- [Versioning](VERSIONING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Agent development instructions](AGENTS.md)

## Human help

```bash
t32
t32 --help
t32 <resource> --help
t32 <resource> <action> --help
```

TRACE32 is a product/trademark of Lauterbach. This is an independent community project and is not affiliated with or endorsed by Lauterbach GmbH.
