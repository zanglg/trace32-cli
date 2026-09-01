# Architecture

`trace32-cli` separates TRACE32 transport/capabilities, debugger semantics, and Agent workflows into three layers.

```text
Layer 2  Skill / workflow
              |
Layer 1  Generic debugger API (GDB-inspired semantics)
              |
Layer 0  Normalized TRACE32 capability adapter (PYRCL-inspired mechanisms)
              |
Backend  PYRCL / future native TRACE32 backend
              |
         TRACE32 PowerView
```

This document describes the current implementation, not a future target architecture.

## Layer 0: normalized TRACE32 capability adapter

Layer 0 models what a TRACE32 backend can do. It remains architecture-neutral and does not implement debugger strategy.

Current responsibilities:

- stable backend contract consumed by Layer 1
- structured TRACE32/PYRCL mechanisms: address, memory, register, breakpoint, symbol, variable
- language bridge: command/function
- PRACTICE/CMM and macros
- direct-access exposure when available
- backend capability discovery
- breakpoint parameter normalization
- backend-specific syntax adaptation such as typed-memory method mapping and PRACTICE argument quoting
- backend error normalization into stable categories

Current implementation:

```text
trace32_cli.layer0.Trace32Backend
trace32_cli.layer0.PyrclBackend
trace32_cli.layer0.BackendCapabilities
trace32_cli.layer0.Trace32BackendError
```

Architecture-specific register names such as `TTBR0_EL1`, `ESR_EL1`, `mstatus`, and `mcause` remain opaque strings. Layer 0 does not maintain architecture register databases or interpret their meaning.

### Layer 0 capability discovery

A connected backend can expose a runtime snapshot of available services/features. The public CLI entry is:

```bash
t32 --json backend capabilities
```

This reports backend mechanics such as register, memory, breakpoint, PRACTICE, and direct-access availability. It is not a CPU-feature database and does not answer questions such as whether the current processor implements EL2 or a particular CSR.

### Layer 0 errors

Backend-specific exceptions are normalized before reaching Layer 1/CLI. Current stable categories include:

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

This allows future backends to map their native failures into the same public contract.

## Layer 1: generic debugger semantics

Layer 1 models debugger meaning rather than TRACE32 command syntax. Its concepts are inspired by GDB semantics, but the public CLI is not a GDB command clone.

Implemented domains:

- target lifecycle/state/info
- execution: continue, halt, compatibility step, instruction step, source step, next, finish, run-to, wait, stop-event inspection
- context: core plus generic OS-aware task context where TRACE32 TASK awareness is available
- register read/write/list
- memory typed/raw read/write/search/compare/fill
- breakpoint/watchpoint lifecycle
- symbol and variable access
- expression/type inspection
- unified location/source resolution
- instruction/disassembly
- stack backtrace and frame current/select/up/down
- program/image/symbol loading

### Unified location model

Program locations use three architecture-neutral forms:

```text
AddressLocation("P:0x80001000")
SymbolLocation("main")
SourceLocation("src/main.c", 42)
```

Location resolution can return available address, symbol, and source metadata. Missing debug information remains missing rather than being guessed.

### Execution and stop events

The execution surface includes:

```text
exec run / continue
exec halt
exec step
exec stepi
exec source-step
exec next
exec finish
exec run-to
exec wait
exec stop-reason
```

Stop-event classification is conservative:

- CLI-initiated halt/step operations have known operation reasons.
- An exact stopped-PC match to an enabled PROGRAM breakpoint may be inferred as a breakpoint stop.
- Other externally triggered stops remain `unknown` unless the backend exposes sufficient evidence.

Stop events expose reason source/confidence so consumers can distinguish known facts from inference.

### Frame and task context

Frame levels are zero-based from the innermost frame. Public operations include:

```bash
t32 --json frame current
t32 --json frame select 2
t32 frame up
t32 frame down
t32 --json stack backtrace
```

Generic TRACE32 OS-awareness task operations include:

```bash
t32 --json context task-current
t32 --json context task-list
t32 --json context task-select worker
```

Task selection changes debugger inspection context; it does not schedule or switch the target task. If TRACE32 OS-awareness is unavailable, the operation reports unsupported rather than manufacturing an OS model.

### Structured expressions and disassembly

Expression evaluation can expose available metadata such as value, type, address, and size. Type description returns available type/size data. Disassembly returns instruction text plus available symbol/source metadata.

These results depend on loaded symbols/debug information and current TRACE32 state.

## Layer 2: Skill/workflow

Layer 2 contains Agent strategy, discovery policy, safety discipline, and workflow orchestration. It does not implement deterministic debugger primitives that belong in Layer 1.

The bundled Skill currently provides policy/guidance and runtime-use discipline. A comprehensive task-oriented workflow library remains separate future work.

## Architecture-specific extensions

Architecture and capability are orthogonal. The generic core intentionally does not include:

- AArch64 register database
- RISC-V register database
- TriCore register database
- AArch64 exception/MMU/page-table decoding
- RISC-V CSR/exception/MMU semantic decoding
- TriCore CSA semantic decoding

Those features should be explicit Layer 1 semantic extensions only when architecture interpretation is required.

## Public CLI routing

The current public assembly is:

```text
t32
  -> trace32_cli.entry
  -> trace32_cli.completed_app
  -> Layer 1 handlers
  -> Layer 1 Debugger
  -> Layer 0 Trace32Backend/PyrclBackend
  -> PYRCL
  -> TRACE32 PowerView
```

`raw cmd`, `raw fnc`, PRACTICE/CMM, macros, and direct-access mechanisms remain explicit TRACE32-oriented escape hatches rather than being hidden inside Agent workflows.

## Design rules

```text
JSON / metadata = facts
Layer 0         = normalized TRACE32 backend capabilities
Layer 1         = deterministic debugger semantics
Layer 2 / Skill = strategy and workflow
```

Prefer Layer 1 for normal debugger operations. Use Layer 0 mechanisms when no higher debugger semantic distinction exists. Use raw/PRACTICE for TRACE32-specific long-tail or vendor workflows.
