"""Layered live regression tests against a TRACE32 PowerView session.

The self-test owns its plan definitions and CLI arguments. ``app.py`` only
registers the command and delegates here, keeping test policy out of CLI bootstrap.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

from . import cli as core
from . import runtime
from .layer0 import PyrclBackend
from .layer1 import Debugger as Layer1Debugger

SUITE_MEMORY = "memory"
SUITE_EXTENDED = "extended"
SUITE_EXECUTION = "execution"
OPTIONAL_SUITES = (SUITE_MEMORY, SUITE_EXTENDED, SUITE_EXECUTION)
DEFAULT_VM_ADDRESS = "VM:0x1000"
VM_SCRATCH_SIZE = 0x100
_TYPE_WIDTH = {"u8": 1, "u16": 2, "u32": 4, "u64": 8, "s64": 8, "f32": 4, "f64": 8}


@dataclass(frozen=True)
class TestPlan:
    """A named selection of optional self-test suites."""

    name: str
    suites: frozenset[str]
    description: str

    def includes(self, suite: str) -> bool:
        return suite in self.suites


def _prefix_suites(count: int) -> frozenset[str]:
    return frozenset(OPTIONAL_SUITES[:count])


TEST_PLANS: dict[str, TestPlan] = {
    "read-only": TestPlan(
        "read-only",
        frozenset(),
        "target/runtime observation only; no requested writes or execution control",
    ),
    "memory": TestPlan(
        "memory",
        _prefix_suites(1),
        "read-only baseline plus initialized TRACE32 host-side VM: scratch round-trips",
    ),
    "extended": TestPlan(
        "extended",
        _prefix_suites(2),
        "memory plan plus temporary debugger/breakpoint-state mutation",
    ),
    "execution": TestPlan(
        "execution",
        _prefix_suites(3),
        "extended plan plus Break/Step/Go execution-control checks",
    ),
    "all": TestPlan(
        "all",
        frozenset(OPTIONAL_SUITES),
        "all registered self-test suites; automatically expands when new suites are registered",
    ),
}


def get_plan(name: str) -> TestPlan:
    try:
        return TEST_PLANS[name]
    except KeyError as exc:
        raise core.CliError(
            "INVALID_TEST_PLAN",
            f"unknown self-test plan: {name}",
            core.EXIT_INVALID_INPUT,
        ) from exc


def capability_metadata() -> dict[str, Any]:
    return {
        "human": "t32 test",
        "machine": "t32 --json test",
        "plans": {
            "read-only": "t32 test",
            "memory": "t32 test --memory",
            "extended": "t32 test --extended",
            "execution": "t32 test --execution",
            "all": "t32 test --all",
        },
        "cumulative_through_execution": True,
        "all_semantics": (
            "--all runs every registered suite; it currently covers the same cases as "
            "--execution and will include future suites automatically"
        ),
        "address_override": "t32 test --address P:0x...",
        "safety": {
            "read-only": "observation only",
            "memory": (
                "initializes and writes a dedicated 256-byte TRACE32 host-side VM: scratch range; "
                "no direct target-memory writes"
            ),
            "extended": (
                "adds temporary breakpoint state; TRACE32 chooses the breakpoint implementation, "
                "so software/on-chip target effects are runtime-dependent"
            ),
            "execution": (
                "adds Break/Step/Go; final running/halted mode is restored when possible, "
                "but executed instructions and their side effects cannot be undone"
            ),
            "all": "runs every registered suite and therefore has the highest current risk",
        },
    }


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add self-test arguments without leaking plan policy into ``app.py``."""

    parser.add_argument("--core", type=int, default=0, help="core used for PC/register checks")
    parser.add_argument(
        "--address",
        help="target address; defaults to P:<current PC>; bare values imply P:",
    )
    parser.add_argument("--length", type=int, default=64, help="target dump length; default: 64")
    parser.add_argument(
        "--vm-address",
        default=DEFAULT_VM_ADDRESS,
        help=(
            f"base of the dedicated {VM_SCRATCH_SIZE}-byte TRACE32 host-side VM: scratch range; "
            f"default: {DEFAULT_VM_ADDRESS}"
        ),
    )

    plans = parser.add_mutually_exclusive_group()
    plans.add_argument(
        "--memory",
        dest="test_plan",
        action="store_const",
        const="memory",
        help="initialize host-side VM: scratch and run memory round-trip tests",
    )
    plans.add_argument(
        "--extended",
        dest="test_plan",
        action="store_const",
        const="extended",
        help="add memory tests plus temporary debugger/breakpoint-state tests",
    )
    plans.add_argument(
        "--execution",
        dest="test_plan",
        action="store_const",
        const="execution",
        help="add all suites through Break/Step/Go execution-control testing",
    )
    plans.add_argument(
        "--all",
        dest="test_plan",
        action="store_const",
        const="all",
        help="run every registered self-test suite; highest-risk test plan",
    )
    parser.set_defaults(test_plan="read-only")


def _error(exc: Exception) -> dict[str, Any]:
    result = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, core.CliError):
        result["code"] = exc.code
    return result


def _record(cases: list[dict[str, Any]], case_id: str, fn: Callable[[], Any]) -> Any:
    try:
        data = fn()
        cases.append({"id": case_id, "status": "pass", "data": data})
        return data
    except Exception as exc:
        cases.append({"id": case_id, "status": "fail", "error": _error(exc)})
        return None


def _skip(cases: list[dict[str, Any]], case_id: str, reason: str) -> None:
    cases.append({"id": case_id, "status": "skip", "reason": reason})


def _number(value: Any) -> int:
    value = core._value(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"expected integer-like value, got {type(value).__name__}")


def _read_pc(dbg, core_index: int) -> dict[str, Any]:
    try:
        reg = dbg.register.read("PC", core=core_index)
    except TypeError:
        reg = dbg.register.read("PC")
    value = _number(reg)
    return {"name": "PC", "core": core_index, "value": value, "hex": f"0x{value:x}"}


def _target_address(explicit: str | None, pc: int | None) -> str | None:
    if explicit:
        return explicit if ":" in explicit else f"P:{explicit}"
    if pc is None:
        return None
    return f"P:0x{pc:x}"


def _vm_address(debugger: Layer1Debugger, text: str, offset: int = 0) -> str:
    address = debugger.address_parse(text if ":" in text else f"VM:{text}")
    access = str(getattr(address, "access", "") or "").upper()
    if access != "VM":
        raise core.CliError(
            "INVALID_TEST_VM_ADDRESS",
            "--vm-address must use the TRACE32 VM: access class",
            core.EXIT_INVALID_INPUT,
        )
    value = getattr(address, "value", None)
    if not isinstance(value, int):
        raise core.CliError(
            "INVALID_TEST_VM_ADDRESS",
            "--vm-address must resolve to a numeric VM: address",
            core.EXIT_INVALID_INPUT,
        )
    return f"VM:0x{value + offset:x}"


def _initialize_vm_scratch(debugger: Layer1Debugger, vm_base: str) -> dict[str, Any]:
    """Initialize the host-side scratch before any preserve/read operation.

    TRACE32 VM: can contain uninitialized locations. The self-test owns this
    dedicated range, so it initializes the complete range before performing
    read/preserve/write/restore round-trips. This never writes target memory.
    """

    data = bytes(VM_SCRATCH_SIZE)
    debugger.memory_write_bytes(vm_base, data)
    _, observed = debugger.memory_dump(vm_base, length=VM_SCRATCH_SIZE)
    if observed != data:
        raise AssertionError("VM scratch initialization verification failed")
    return {"address": vm_base, "length": VM_SCRATCH_SIZE, "initialized": True}


def _preserve_bytes(debugger: Layer1Debugger, address_text: str, length: int) -> bytes:
    _, data = debugger.memory_dump(address_text, length=length)
    return data


def _restore_bytes(debugger: Layer1Debugger, address_text: str, data: bytes) -> None:
    debugger.memory_write_bytes(address_text, data)


def _raw_vm_roundtrip(debugger: Layer1Debugger, address_text: str) -> dict[str, Any]:
    pattern = bytes.fromhex("00112233445566778899aabbccddeeff")
    original = _preserve_bytes(debugger, address_text, len(pattern))
    try:
        debugger.memory_write_bytes(address_text, pattern)
        _, observed = debugger.memory_dump(address_text, length=len(pattern))
        if observed != pattern:
            raise AssertionError(f"round-trip mismatch: {observed.hex()} != {pattern.hex()}")
        return {"address": address_text, "length": len(pattern), "hex": observed.hex()}
    finally:
        _restore_bytes(debugger, address_text, original)


def _typed_vm_roundtrip(
    debugger: Layer1Debugger,
    address_text: str,
    type_name: str,
    values: list[Any],
    *,
    byteorder: str | None = None,
) -> dict[str, Any]:
    original = _preserve_bytes(debugger, address_text, _TYPE_WIDTH[type_name] * len(values))
    try:
        debugger.memory_write_typed(
            address_text,
            values,
            type_name=type_name,
            byteorder=byteorder,
        )
        _, actual = debugger.memory_read_typed(
            address_text,
            type_name=type_name,
            count=len(values),
            byteorder=byteorder,
        )
        if type_name in {"f32", "f64"}:
            for expected, observed in zip(values, actual):
                if not math.isclose(float(expected), float(observed), rel_tol=1e-6, abs_tol=1e-6):
                    raise AssertionError(f"float mismatch: {observed} != {expected}")
        elif actual != values:
            raise AssertionError(f"typed round-trip mismatch: {actual!r} != {values!r}")
        return {
            "address": address_text,
            "type": type_name,
            "count": len(values),
            "value": actual,
            "byteorder": byteorder,
        }
    finally:
        _restore_bytes(debugger, address_text, original)


def _byteorder_vm_roundtrip(
    debugger: Layer1Debugger,
    address_text: str,
    byteorder: str,
    expected_hex: str,
) -> dict[str, Any]:
    original = _preserve_bytes(debugger, address_text, 4)
    try:
        debugger.memory_write_typed(
            address_text,
            [0x11223344],
            type_name="u32",
            byteorder=byteorder,
        )
        _, observed = debugger.memory_dump(address_text, length=4)
        if observed.hex() != expected_hex:
            raise AssertionError(f"byteorder mismatch: {observed.hex()} != {expected_hex}")
        return {"address": address_text, "byteorder": byteorder, "hex": observed.hex()}
    finally:
        _restore_bytes(debugger, address_text, original)


def _run_memory_tests(
    debugger: Layer1Debugger,
    cases: list[dict[str, Any]],
    vm_base: str,
) -> None:
    specs = [
        ("vm.raw", 0x00, lambda a: _raw_vm_roundtrip(debugger, a)),
        ("vm.u8", 0x20, lambda a: _typed_vm_roundtrip(debugger, a, "u8", [1, 2, 255])),
        ("vm.u16", 0x30, lambda a: _typed_vm_roundtrip(debugger, a, "u16", [0x1122, 0x3344])),
        ("vm.u32", 0x40, lambda a: _typed_vm_roundtrip(debugger, a, "u32", [0x11223344, 0x55667788])),
        ("vm.u64", 0x50, lambda a: _typed_vm_roundtrip(debugger, a, "u64", [0x1122334455667788])),
        ("vm.s64", 0x60, lambda a: _typed_vm_roundtrip(debugger, a, "s64", [-123456789])),
        ("vm.f32", 0x70, lambda a: _typed_vm_roundtrip(debugger, a, "f32", [1.5])),
        ("vm.f64", 0x80, lambda a: _typed_vm_roundtrip(debugger, a, "f64", [3.141592653589793])),
        ("vm.multi_u32", 0x90, lambda a: _typed_vm_roundtrip(debugger, a, "u32", [1, 2, 3, 4])),
        ("vm.little_endian", 0xB0, lambda a: _byteorder_vm_roundtrip(debugger, a, "little", "44332211")),
        ("vm.big_endian", 0xC0, lambda a: _byteorder_vm_roundtrip(debugger, a, "big", "11223344")),
    ]

    initialized = _record(cases, "vm.initialize", lambda: _initialize_vm_scratch(debugger, vm_base))
    if initialized is None:
        for case_id, _offset, _fn in specs:
            _skip(cases, case_id, "VM scratch initialization failed")
        return

    for case_id, offset, fn in specs:
        address = _vm_address(debugger, vm_base, offset)
        _record(cases, case_id, lambda address=address, fn=fn: fn(address))


def _breakpoint_lifecycle(dbg, address_text: str, core_index: int) -> dict[str, Any]:
    address = core._address(dbg, address_text)
    before = len(list(dbg.breakpoint.list()))
    bp = None
    deleted = False
    try:
        bp = dbg.breakpoint.set(address=address, core=core_index)
        bp.disable()
        bp.enable()
        bp.delete()
        deleted = True
    finally:
        # Cleanup is best-effort because a partially-created breakpoint is more dangerous
        # than preserving the original exception from the test operation.
        if bp is not None and not deleted:
            try:
                bp.delete()
            except Exception:
                pass

    after = len(list(dbg.breakpoint.list()))
    if after != before:
        raise AssertionError(f"breakpoint cleanup mismatch: before={before}, after={after}")
    return {"address": address_text, "core": core_index, "before": before, "after": after}


def _running(dbg) -> bool:
    return bool(core._value(dbg.fnc("STATE.RUN()")))


def _command_and_expect(dbg, command: str, expected_running: bool) -> dict[str, Any]:
    dbg.cmd(command)
    actual = _running(dbg)
    if actual != expected_running:
        raise AssertionError(
            f"{command} state mismatch: expected running={expected_running}, got {actual}"
        )
    return {"running": actual}


def _run_execution_tests(dbg, cases: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        initial_running = _running(dbg)
    except Exception as exc:
        cases.append({"id": "execution.initial_state", "status": "fail", "error": _error(exc)})
        return {"initial_running": None, "final_running": None, "restored_mode": False}

    _record(cases, "execution.halt", lambda: _command_and_expect(dbg, "Break", False))
    _record(cases, "execution.step", lambda: _command_and_expect(dbg, "Step", False))
    _record(cases, "execution.run", lambda: _command_and_expect(dbg, "Go", True))

    def restore():
        if initial_running:
            if not _running(dbg):
                dbg.cmd("Go")
        elif _running(dbg):
            dbg.cmd("Break")
        final_running = _running(dbg)
        if final_running != initial_running:
            raise AssertionError(
                f"execution mode restore failed: initial={initial_running}, final={final_running}"
            )
        return {"initial_running": initial_running, "final_running": final_running}

    restored = _record(cases, "execution.restore_state", restore)
    return {
        "initial_running": initial_running,
        "final_running": restored.get("final_running") if isinstance(restored, dict) else None,
        "restored_mode": isinstance(restored, dict),
    }


class SelfTestRunner:
    """Execute one self-test plan while keeping shared state in one place."""

    def __init__(self, dbg, args):
        if args.length < 1:
            raise core.CliError("INVALID_LENGTH", "--length must be >= 1", core.EXIT_INVALID_INPUT)

        self.dbg = dbg
        self.layer1 = Layer1Debugger(PyrclBackend(dbg))
        self.args = args
        self.plan = get_plan(getattr(args, "test_plan", "read-only"))
        self.cases: list[dict[str, Any]] = []
        self.core_index = getattr(args, "core", 0)
        self.target_address: str | None = None
        self.execution_result: dict[str, Any] | None = None

        config_meta = getattr(args, "_config_meta", {"sources": {}})
        self.context: dict[str, Any] = {
            "plan": self.plan.name,
            "profile": getattr(args, "profile", None),
            "host": getattr(args, "host", None),
            "port": getattr(args, "port", None),
            "protocol": getattr(args, "protocol", None),
            "host_source": config_meta.get("sources", {}).get("host"),
            "core": self.core_index,
            "requested_address": getattr(args, "address", None),
            "length": args.length,
            "vm_scratch": None,
            "vm_scratch_size": None,
        }

        if self.plan.includes(SUITE_MEMORY):
            self.context["vm_scratch"] = _vm_address(self.layer1, args.vm_address)
            self.context["vm_scratch_size"] = VM_SCRATCH_SIZE

    def run(self) -> dict[str, Any]:
        self._run_baseline()
        if self.plan.includes(SUITE_MEMORY):
            _run_memory_tests(self.layer1, self.cases, self.context["vm_scratch"])
        if self.plan.includes(SUITE_EXTENDED):
            self._run_extended()
        if self.plan.includes(SUITE_EXECUTION):
            self.execution_result = _run_execution_tests(self.dbg, self.cases)
        return self._report()

    def _run_baseline(self) -> None:
        _record(self.cases, "runtime.target_info", lambda: runtime.h_target_info(self.dbg, self.args))
        _record(self.cases, "runtime.target_state", lambda: core.h_target_state(self.dbg, self.args))
        _record(self.cases, "runtime.cpu", lambda: {"value": core._value(self.dbg.fnc("CPU()"))})
        _record(
            self.cases,
            "runtime.state_run",
            lambda: {"value": core._value(self.dbg.fnc("STATE.RUN()"))},
        )

        pc_result = _record(self.cases, "reg.pc", lambda: _read_pc(self.dbg, self.core_index))
        pc = pc_result["value"] if isinstance(pc_result, dict) else None
        self.context["pc"] = f"0x{pc:x}" if isinstance(pc, int) else None

        def list_registers():
            values = core.h_reg_list(
                self.dbg, SimpleNamespace(core=self.core_index, unit="CPU", contains=None)
            )
            return {"count": len(values)}

        _record(self.cases, "reg.enumerate_cpu", list_registers)

        def breakpoint_enums():
            values = runtime.h_bp_enums(self.dbg, self.args)
            return {key: len(value) for key, value in values.items()}

        _record(self.cases, "bp.enums", breakpoint_enums)
        _record(
            self.cases,
            "bp.list",
            lambda: {"count": len(list(self.dbg.breakpoint.list()))},
        )

        self.target_address = _target_address(self.context["requested_address"], pc)
        self.context["target_address"] = self.target_address
        if self.target_address is None:
            reason = "PC could not be read and --address was not provided"
            _skip(self.cases, "mem.target_dump", reason)
            _skip(self.cases, "mem.target_u8", reason)
            return

        def target_dump():
            address, data = self.layer1.memory_dump(self.target_address, length=self.args.length)
            return {"address": str(address), "length": len(data), "hex": data.hex()}

        def target_u8():
            address, values = self.layer1.memory_read_typed(
                self.target_address,
                type_name="u8",
                count=min(self.args.length, 16),
            )
            return {
                "address": str(address),
                "type": "u8",
                "count": len(values),
                "value": values,
            }

        _record(self.cases, "mem.target_dump", target_dump)
        _record(self.cases, "mem.target_u8", target_u8)

    def _run_extended(self) -> None:
        if self.target_address is None:
            _skip(self.cases, "extended.breakpoint_lifecycle", "no target address available")
            return
        _record(
            self.cases,
            "extended.breakpoint_lifecycle",
            lambda: _breakpoint_lifecycle(self.dbg, self.target_address, self.core_index),
        )

    def _report(self) -> dict[str, Any]:
        passed = sum(case["status"] == "pass" for case in self.cases)
        failed = sum(case["status"] == "fail" for case in self.cases)
        skipped = sum(case["status"] == "skip" for case in self.cases)
        return {
            "plan": self.plan.name,
            "suites": list(suite for suite in OPTIONAL_SUITES if suite in self.plan.suites),
            "safety": {
                "direct_target_memory_writes_requested": False,
                "vm_scratch_host_side": self.plan.includes(SUITE_MEMORY),
                "vm_scratch_initialized": self.plan.includes(SUITE_MEMORY),
                "vm_scratch_size": VM_SCRATCH_SIZE if self.plan.includes(SUITE_MEMORY) else None,
                "breakpoint_state_mutation": self.plan.includes(SUITE_EXTENDED),
                "breakpoint_implementation_runtime_dependent": self.plan.includes(SUITE_EXTENDED),
                "execution_control": self.plan.includes(SUITE_EXECUTION),
                "execution_mode_restored": (
                    self.execution_result.get("restored_mode")
                    if isinstance(self.execution_result, dict)
                    else None
                ),
            },
            "context": self.context,
            "summary": {"passed": passed, "failed": failed, "skipped": skipped},
            "cases": self.cases,
        }


def run_self_test(dbg, args) -> dict[str, Any]:
    return SelfTestRunner(dbg, args).run()


def _case_detail(case: dict[str, Any]) -> str:
    if case["status"] == "fail":
        return case.get("error", {}).get("message", "")
    if case["status"] == "skip":
        return case.get("reason", "")
    data = case.get("data")
    if not isinstance(data, dict):
        return ""
    if "hex" in data and case["id"] == "reg.pc":
        return str(data["hex"])
    if "count" in data:
        return f"count={data['count']}"
    if "value" in data and len(data) == 1:
        return str(data["value"])
    if "length" in data:
        return f"{data['length']} bytes"
    return ""


def format_human_report(report: dict[str, Any]) -> str:
    context = report.get("context", {})
    plan = report.get("plan") or context.get("plan") or "read-only"
    lines = [
        "TRACE32 CLI Self-Test",
        "",
        f"Plan: {plan}",
        "",
        "Connection",
        f"  PowerView:   {context.get('host')}:{context.get('port')}",
        f"  host source: {context.get('host_source')}",
        f"  profile:     {context.get('profile') or '-'}",
        f"  core:        {context.get('core')}",
        f"  PC:          {context.get('pc') or '-'}",
        f"  target addr: {context.get('target_address') or '-'}",
        f"  VM scratch:  {context.get('vm_scratch') or 'not used'}",
        "",
        "Cases",
    ]
    labels = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}
    for case in report.get("cases", []):
        detail = _case_detail(case)
        suffix = f"  {detail}" if detail else ""
        lines.append(
            f"  {labels.get(case['status'], case['status'].upper()):4}  {case['id']}{suffix}"
        )

    summary = report.get("summary", {})
    lines.extend(
        [
            "",
            "Summary",
            f"  {summary.get('passed', 0)} passed",
            f"  {summary.get('failed', 0)} failed",
            f"  {summary.get('skipped', 0)} skipped",
        ]
    )

    safety = report.get("safety", {})
    if safety.get("vm_scratch_host_side"):
        lines.extend(
            [
                "",
                "NOTE: the memory suite initializes a dedicated 256-byte TRACE32 host-side VM:",
                "scratch range. It does not write target memory; prior VM scratch contents are not preserved.",
            ]
        )
    if safety.get("breakpoint_state_mutation"):
        lines.extend(
            [
                "",
                "NOTE: this plan creates a temporary breakpoint. TRACE32 selects the breakpoint",
                "implementation, so software/on-chip target effects depend on runtime configuration.",
            ]
        )
    if safety.get("execution_control"):
        lines.extend(
            [
                "",
                "WARNING: this plan runs Break/Step/Go. The final running/halted mode is restored",
                "when possible, but instructions executed by Step/Go and their side effects cannot be undone.",
            ]
        )
    return "\n".join(lines)


def h_test(dbg, args):
    report = run_self_test(dbg, args)
    if report["summary"]["failed"]:
        raise core.CliError(
            "TEST_FAILED",
            f"{report['summary']['failed']} TRACE32 CLI self-test case(s) failed",
            core.EXIT_OPERATION,
            details=report,
        )
    return report