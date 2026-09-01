---
name: t32
description: >
  Use the installed `t32` CLI to inspect and control embedded targets through
  Lauterbach TRACE32. Use for register, memory, symbol, variable, breakpoint,
  PRACTICE, execution-control, configuration, testing, and low-level TRACE32 debugging tasks.
---

# TRACE32 Debug Skill

Use the installed `t32` CLI as the primitive interface to TRACE32.

## Discover before assuming

```bash
t32 --json capabilities
t32 --json schema
```

Before debugging a newly configured environment:

```bash
t32 --json profile current
t32 --json doctor
```

After connection:

```bash
t32 --json target info
t32 --json reg list --core 0
t32 --json bp enums
```

## Connection configuration

Persistent layers:

```text
~/.config/trace32-cli/config.toml
<repo>/.trace32/config.toml
<repo>/.trace32/config.local.toml
```

Use zero configuration for a single local PowerView at `localhost:20001` unless the user requests a named profile or different port. A named profile must resolve an explicit host and never falls back to implicit localhost.

When asked to configure a project:

1. Inspect `capabilities`, `profile list`, and `profile current` first.
2. Preserve existing configuration.
3. Put stable/shareable target definitions in `.trace32/config.toml`.
4. Put machine-specific endpoints in `.trace32/config.local.toml` and ensure it is gitignored.
5. Verify `sources.host` with `profile current`, then connectivity with `doctor`.
6. Stop setup verification after `doctor`; do not attach or change target state merely to validate configuration.
7. Do not run live self-tests as part of installation or configuration verification unless the user explicitly asks for regression testing.

If this Skill was installed during the current Agent session but the client cannot dynamically load it, `t32 skill show` provides the same guidance as text.

## Live self-test plans

Use the lowest-risk plan that answers the question:

```bash
t32 test              # observation only
t32 test --memory     # add TRACE32 VM: write/read/restore tests
t32 test --extended   # add temporary breakpoint lifecycle
t32 test --execution  # add Break/Step/Go
t32 test --all        # every registered suite; highest risk
```

For Agent/CI parsing, add global `--json` explicitly:

```bash
t32 --json test --all
```

`VM:` is TRACE32 debugger-side virtual memory, not target `D:`/`P:` memory and not CPU/MMU virtual memory.

Safety rules:

- Default `t32 test` is the crash-preservation choice.
- `--memory` writes only TRACE32 VM scratch and restores it.
- `--extended` mutates breakpoint/debugger state; TRACE32 chooses software/on-chip breakpoint implementation.
- `--execution` executes target instructions. Restoring running/halted mode cannot undo executed instructions or side effects.
- `--all` includes every current/future registered self-test suite; never run it merely to check connectivity.

## Preferred primitive order

```text
reg / mem / sym / var / bp / macro / practice
        ↓
raw fnc
        ↓
raw cmd
```

Prefer typed primitives over raw TRACE32 commands.

## Architecture boundary

The CLI is architecture-neutral. Use runtime facts instead of assuming a hard-coded register catalog.

## Observation first

Preserve evidence before state-changing operations. State-changing operations include attach, execution control, register/memory/variable writes, breakpoint mutation, PRACTICE execution, raw commands, and higher-risk self-test plans.

## Skill installation

```bash
t32 skill status
t32 skill show
```

The installed Skill is bundled with the CLI version. Installed `capabilities` and `schema` are the command source of truth.
