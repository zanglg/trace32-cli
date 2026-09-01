# Layer 0 / Layer 1 implementation status

This document records the current completion boundary of the generic debugger core. It distinguishes implemented software contracts, runtime-dependent TRACE32 behavior, and intentionally deferred extensions.

## Summary

```text
Layer 0 normalized TRACE32 capability adapter   implemented for current generic core
Layer 1 generic debugger semantics              implemented for current generic core
Software CI / parser / packaging validation     complete
Representative PowerView + physical target      passed registered self-test suites
Cross-target / cross-runtime validation matrix   incomplete
Architecture-specific semantic extensions       intentionally deferred
Layer 2 workflow library                        not part of Layer 0/1 completion
```

"Core complete" means the currently defined architecture-neutral Layer 0/1 scope is implemented. It does not mean every TRACE32 feature or every debugger feature is implemented.

## Layer 0

### Implemented

- stable `Trace32Backend` contract
- `PyrclBackend` implementation
- address parse/create
- register read/write/list/multi-read
- raw and typed memory read/write
- breakpoint set/list/delete/enable/disable/clear
- breakpoint runtime enum/parameter discovery
- symbol query by name/address
- variable read/write
- command/function bridges
- PRACTICE/CMM execution with arguments and timeout semantics
- PRACTICE macro get/set
- direct-access availability/exposure
- runtime backend capability snapshot
- stable backend error taxonomy and PyRCL error normalization

### Runtime-dependent validation still required

Software tests verify adapter contracts with fake backends and installed PyRCL compatibility. A representative live PowerView + physical-target run has passed every currently registered `t32 test --all` case, including Layer 1 → Layer 0 raw/typed VM memory, endianness, breakpoint lifecycle, and Break/Step/Go execution-control checks.

The following still require broader live TRACE32/PowerView validation across representative environments:

- exact behavior of typed memory accesses for target-specific access classes
- breakpoint implementation/action combinations on different real targets
- PRACTICE timeout/non-blocking behavior in actual scripts
- direct-access availability and behavior across PowerView/PyRCL versions
- exact backend error mappings for live target/connection failure modes

### Intentionally not Layer 0 work

Layer 0 must not gain debugger semantics such as stop-reason inference, frame meaning, source semantics, task semantics, or architecture-specific register interpretation.

## Layer 1

### Implemented

- target attach/detach/up/reset/state/info
- execution continue/halt/step/instruction-step/source-step/next/finish/run-to/wait
- conservative stop-event model with reason source/confidence
- core context propagation
- generic TRACE32 OS-awareness task current/list/select
- register read/write/list
- typed/raw memory operations plus search/compare/fill
- breakpoint/watchpoint lifecycle
- symbol/variable operations
- structured expression evaluation and type description
- unified address/symbol/source `Location` model
- source/current/source-list/location resolution
- instruction/disassembly result model
- stack backtrace
- frame current/select/up/down
- program listing and ELF/symbol/binary loading

### Runtime-dependent validation still required

The registered live self-test suite covers a useful generic core subset, but it is not equivalent to every public Layer 1 command. These operations still depend on TRACE32 command/function behavior, loaded debug information, target state, or OS awareness and need broader live integration coverage:

- `Step.Asm`, `Step.Hll`, `Step.Over`, `Step.Return` semantics on representative targets
- stop-reason inference against real breakpoint/watchpoint/exception stops
- source/location resolution with real DWARF/debug information
- structured `Var.VALUE/TYPEOF/ADDRESS/SIZEOF` results across C/C++ expressions and types
- disassembly metadata across architectures/instruction modes
- stack unwinding and frame selection across real call stacks
- TASK awareness across representative RTOS/Linux configurations
- `Data.LOAD.*` image/symbol loading behavior

### Known conservative boundary

The current PyRCL path does not expose a generic asynchronous stop-event stream with a universally normalized reason. Therefore Layer 1 does not claim reliable classification for every external stop. Unknown remains a valid and intentional result when evidence is insufficient.

## Explicitly deferred extensions

The following are outside the current generic core and should not be counted as unfinished Layer 0/1 core bugs:

```text
Architecture semantics
├── AArch64 exception decoding
├── AArch64 MMU/page-table analysis
├── RISC-V CSR/exception/MMU decoding
└── TriCore CSA semantics

Advanced debugger extensions
├── full process/inferior model
├── richer OS-specific process/thread integration
├── hardware trace subsystem
├── record/replay or reverse debugging
└── architecture-specific trace analysis
```

Architecture-specific register names remain opaque parameters until one of these semantic extensions actually needs to interpret them.

## Validation status

The `0.1.0` release candidate requires and passes software-side checks through GitHub Actions:

```text
Python 3.9–3.13
ruff check .
python -m pytest
CLI smoke tests
python -m build
```

Representative live validation also passed every currently registered case in:

```bash
t32 test --all
```

against a real TRACE32 PowerView session and physical target. This validates the registered self-test surface; it does not claim exhaustive compatibility across all TRACE32 versions, processor families, OS-awareness configurations, source/debug-info combinations, or optional backend services.

## Next completion gate

The next meaningful Layer 0/1 work is not broad API expansion. It is a broader real-target integration matrix that exercises representative PowerView/target/OS-awareness combinations and converts confirmed runtime differences into tests or narrow adapter fixes.
