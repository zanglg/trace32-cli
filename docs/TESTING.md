# Live regression testing

`t32 test` runs a one-connection regression plan against a live TRACE32 PowerView session. Cases continue after individual failures so one run yields a useful diagnostic report.

Self-tests are post-setup regression tools. They are not required for CLI installation, configuration, or PowerView connectivity verification; use `doctor` for setup verification.

## Output contract

Human-readable output is the default:

```bash
t32 test
```

Use explicit JSON for Agents, CI, or scripts:

```bash
t32 --json test
```

## Test plans

| Plan | Command | Included suites | Risk |
| --- | --- | --- | --- |
| Read-only | `t32 test` | baseline | lowest |
| Memory | `t32 test --memory` | baseline + memory | low |
| Extended | `t32 test --extended` | baseline + memory + extended | medium |
| Execution | `t32 test --execution` | baseline + memory + extended + execution | high |
| All | `t32 test --all` | every registered suite | highest/current and future |

`--memory`, `--extended`, `--execution`, and `--all` are mutually exclusive plan selectors. `--all` currently executes the same registered suites as `--execution`, but its semantic contract is different: new self-test suites are automatically included by `--all`.

## Baseline: `t32 test`

The default plan performs observation only:

- runtime capability queries (`target info`, state, `CPU()`, `STATE.RUN()`)
- current `PC` read and CPU register enumeration
- breakpoint enum/list reads
- target memory reads using `P:<PC>` by default

It does not request attach, target memory/register/variable writes, breakpoint creation, PRACTICE, raw commands, or execution control.

## Memory: `--memory`

Adds write/read/restore round-trips in TRACE32 `VM:` virtual memory:

- raw bytes
- `u8`, `u16`, `u32`, `u64`, `s64`
- `f32`, `f64`
- multi-element `u32`
- explicit little/big endian checks

Each case saves the original VM bytes and restores them in `finally` cleanup.

### What `VM:` means

`VM:` is the TRACE32 virtual-memory access class: debugger-side memory managed by TRACE32. It is not target `D:` data memory, target `P:` program memory, or the debugged CPU's MMU virtual address space. This makes it useful for testing PYRCL memory primitives without deliberately writing target RAM/code.

The default scratch base is `VM:0x1000`; override it with:

```bash
t32 test --memory --vm-address VM:0x4000
```

## Extended: `--extended`

Adds a temporary breakpoint lifecycle at the selected target address:

```text
set → disable → enable → delete → verify breakpoint count restored
```

Cleanup is best-effort even when an intermediate operation fails.

Important: TRACE32 chooses the breakpoint implementation. Depending on target/debugger configuration, a breakpoint may be software- or on-chip-backed. Therefore `--extended` changes debugger/breakpoint state and may have target-visible effects; do not treat it as an observation-only crash-preservation plan.

## Execution: `--execution`

Adds:

```text
Break → Step → Go → restore initial running/halted mode when possible
```

This plan **executes target instructions**. Restoring the final running/halted mode does not undo instructions already executed by Step/Go, or their register, memory, peripheral, timing, or external side effects. Use only on a target where such execution is acceptable.

## All: `--all`

`--all` means “run every self-test suite registered by this installed CLI.” It currently includes memory, extended, and execution suites. Future suites are included automatically without changing the meaning of `--execution`.

Use `--all` only when the target is explicitly available for destructive/high-risk regression testing.

## Address selection

Baseline target reads and the extended breakpoint lifecycle use the current PC by default:

```text
P:<PC>
```

Override it with:

```bash
t32 test --address D:0x80000000
t32 test --extended --address P:0x80001000
```

A bare address is interpreted as program memory:

```bash
t32 test --address 0x80001000
# P:0x80001000
```

Other controls:

```bash
t32 test --core 1
t32 test --length 128
```

## Failure contract

A successful plan exits `0`. If one or more required cases fail, `t32 test` exits `12` with `TEST_FAILED`.

Human mode prints case-level PASS/FAIL/SKIP output. JSON mode retains the complete report under `error.details`, including plan, selected suites, safety metadata, endpoint provenance, PC/address context, and every case result.
