---
name: t32
description: >
  Use the installed `t32` CLI to inspect and control embedded targets through
  Lauterbach TRACE32. Use for register, memory, source, stack, expression,
  breakpoint/watchpoint, PRACTICE, execution-control, configuration, testing,
  and low-level TRACE32 debugging tasks.
---

# TRACE32 Debug Skill

Use the installed `t32` CLI as the debugger interface to TRACE32.

## Discover before assuming

Always discover the installed public contract first:

```bash
t32 --json capabilities
t32 --json schema
```

Before debugging a newly configured environment:

```bash
t32
t32 --json profile current
t32 --json doctor
```

Bare `t32` is read-only and shows the resolved project root, profile, endpoint, and config files without connecting to PowerView.

After connection, discover runtime/backend facts rather than assuming target capabilities:

```bash
t32 --json backend capabilities
t32 --json target info
t32 --json exec state
t32 --json context current
t32 --json reg list --core 0
t32 --json bp enums
```

If TRACE32 OS-awareness is configured, task context can also be discovered:

```bash
t32 --json context task-current
t32 --json context task-list
```

## Layering and command preference

```text
Layer 2  Skill/workflow strategy
    ↓
Layer 1  generic debugger semantics
    ↓
Layer 0  TRACE32/PYRCL capabilities
    ↓
PowerView
```

Prefer, in order:

```text
Layer 1 structured debugger operations
    ↓
Layer 0 structured services/capability discovery
    ↓
raw fnc
    ↓
raw cmd
    ↓
PRACTICE/CMM for explicit TRACE32-specific workflows
```

Do not reimplement deterministic generic debugger behavior in prompts or ad-hoc CMM when the CLI exposes a structured operation.

## Generic debugger semantics

Execution:

```bash
t32 --json exec state
t32 --json exec halt
t32 --json exec run
t32 --json exec stepi
t32 --json exec source-step
t32 --json exec next
t32 --json exec finish
t32 --json exec run-to main --kind symbol
t32 --json exec wait --timeout 5
t32 --json exec stop-reason
```

Program state and source semantics:

```bash
t32 --json reg read PC SP
t32 --json mem read 0x1000 --type u32
t32 --json source current
t32 --json source resolve main --kind symbol
t32 --json insn current
t32 --json stack backtrace
t32 --json frame current
t32 --json expr eval 'foo->state'
t32 --json type describe 'foo->state'
```

`expr eval` is structured and may include value, type, address, and size. Disassembly may include source/symbol metadata. Use the returned fields that are actually present; do not manufacture missing metadata.

Locations are architecture-neutral addresses, symbols, or source locations. Use `schema` for exact `--kind`/`--line` syntax.

## Stop-reason discipline

Treat `exec stop-reason` confidence explicitly.

The CLI reports a known reason for operations it initiated, such as explicit halt/step. It may infer `breakpoint` only when the stopped PC exactly matches an enabled PROGRAM breakpoint. If TRACE32/PYRCL does not expose enough evidence for an externally-triggered stop, the reason remains `unknown`.

Do not convert `unknown` into `watchpoint`, `exception`, or another cause without additional evidence.

## Frame and task context

Frame levels are zero-based from the innermost frame:

```bash
t32 --json frame current
t32 --json frame select 2
t32 frame up
t32 frame down
```

When OS-awareness is available:

```bash
t32 --json context task-current
t32 --json context task-list
t32 --json context task-select worker
```

`context task-select` uses TRACE32 `Frame.TASK`; it changes debugger view context, not target scheduling. If task enumeration returns `UNSUPPORTED_OPERATION`, do not assume a particular RTOS task model is available.

## Architecture boundary

The generic CLI does not maintain a hard-coded AArch64, RISC-V, or TriCore register database. Architecture-specific register names are opaque parameters passed to TRACE32/PYRCL:

```bash
t32 --json reg read TTBR0_EL1
t32 --json reg read ESR_EL1
t32 --json reg read mstatus
t32 --json reg read mcause
```

Do not invent per-architecture basic register commands. Exception/MMU/privilege/CSA decoding belongs to architecture-specific semantic extensions that are not part of the current generic core.

## Breakpoints and watchpoints

Discover runtime-supported breakpoint parameters when needed:

```bash
t32 --json bp enums
```

Prefer structured operations:

```bash
t32 --json bp add main --kind symbol
t32 --json bp list
t32 --json watch add 0x1000 --access write
t32 --json watch list
```

Breakpoint indices can change after mutations; list again before acting if debugger state may have changed.

## PRACTICE and raw escape hatches

PRACTICE supports script arguments and completion timeout:

```bash
t32 practice run init.cmm cpu0 fast
t32 practice run init.cmm cpu0 --timeout 10
t32 practice run init.cmm --timeout 0
```

Default timeout behavior waits indefinitely. `--timeout 0` starts without polling for completion.

Use `raw fnc`, `raw cmd`, or PRACTICE only when the task genuinely needs TRACE32-specific behavior not represented by the structured generic API.

## Stable errors

Layer 0 normalizes backend failures into stable categories such as `REGISTER_NOT_FOUND`, `MEMORY_ACCESS_ERROR`, `BREAKPOINT_NOT_FOUND`, `PRACTICE_ERROR`, `UNSUPPORTED_OPERATION`, and `NOT_CONNECTED`.

Use the machine-readable error `code`, `details.operation`, and `recoverable` fields for recovery decisions instead of parsing backend exception text.

## Connection configuration

Persistent configuration has two levels:

```text
~/.config/trace32-cli/config.toml
<project>/.trace32/config.toml
```

The project file overrides user defaults. Project configuration is discovered by walking upward from the current directory and selecting the nearest `.trace32/config.toml`; it is not required to live at the Git top-level.

Use zero configuration for a single local PowerView at `localhost:20001` unless a named profile or different endpoint is requested. A named profile must resolve an explicit host and never falls back to implicit localhost.

When configuring a project:

1. Run bare `t32` and confirm the expected project root, profile, endpoint, and config file.
2. Inspect `capabilities`, `profile list`, and `profile current`.
3. Keep workstation-wide defaults in `~/.config/trace32-cli/config.toml`.
4. Put normal project-specific profiles and endpoints directly in `.trace32/config.toml`.
5. Use CLI options or `--config FILE` for temporary/machine-specific overrides rather than creating another persistent overlay file.
6. Verify endpoint provenance with `profile current`, then connectivity with `doctor`.
7. Stop setup verification after `doctor`; do not mutate target state merely to verify installation/configuration.
8. Run live self-tests only when regression testing is explicitly needed.

If a newly installed Skill cannot be dynamically loaded in the current Agent session, use `t32 skill show`.

## Observation first

Preserve evidence before state-changing operations. For crash/debug-stop analysis, capture at least:

```bash
t32 --json target info
t32 --json exec stop-reason
t32 --json reg read PC SP
t32 --json source current
t32 --json insn current
t32 --json stack backtrace
```

Then mutate state only when required.

State-changing operations include attach/detach/reset/up, execution control, register/memory/variable/expression writes, frame/task context selection, breakpoint/watchpoint mutation, image loading, PRACTICE execution, raw commands, and higher-risk self-tests.

## Live self-test plans

Use the lowest-risk plan that answers the question:

```bash
t32 test              # observation only
t32 test --memory     # add TRACE32 VM: write/read/restore
t32 test --extended   # add temporary breakpoint lifecycle
t32 test --execution  # add Break/Step/Go
t32 test --all        # every registered suite; highest risk
```

For machine parsing, use global `--json` explicitly.

## Runtime validation boundary

Repository CI validates the software/API contract without real target hardware. Runtime-dependent TRACE32 behavior still depends on PowerView version, target state, debug information, CPU support, and OS-awareness.

Do not claim a runtime-dependent operation is supported merely because it exists in `schema`; use `backend capabilities`, runtime discovery, the operation result, and real-target testing where appropriate.

## Skill installation

```bash
t32 skill status
t32 skill show
```

The installed Skill is bundled with the CLI version. Installed `capabilities` and `schema` are the command source of truth.
