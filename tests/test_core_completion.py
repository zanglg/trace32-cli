from __future__ import annotations

import enum
import json
from types import SimpleNamespace

import pytest

from trace32_cli.entry import build_parser, main
from trace32_cli.layer0 import BackendErrorCode, PyrclBackend, Trace32BackendError
from trace32_cli.layer1 import Debugger, StopReason


class BreakpointPrototype:
    class Type(enum.IntEnum):
        PROGRAM = 1
        READ = 2
        WRITE = 4
        RW = 6

    class Impl(enum.IntEnum):
        AUTO = 0
        SOFT = 1
        ONCHIP = 2
        HARD = 4
        MARK = 8

    class Action(enum.IntEnum):
        NONE = 0
        STOP = 1


class BreakpointService:
    def __call__(self):
        return BreakpointPrototype()

    def list(self):
        return []


class FakeRawDebugger:
    def __init__(self):
        self.address = SimpleNamespace(from_string=lambda value: value)
        self.memory = SimpleNamespace()
        self.register = SimpleNamespace()
        self.breakpoint = BreakpointService()
        self.symbol = SimpleNamespace()
        self.variable = SimpleNamespace()
        self.practice = SimpleNamespace()
        self.directaccess = SimpleNamespace()
        self.cmm_calls = []
        self.cmd = lambda command: None
        self.fnc = lambda expression: None

    def cmm(self, command, *, timeout=None):
        self.cmm_calls.append((command, timeout))


def test_layer0_capability_snapshot_and_breakpoint_parameters():
    backend = PyrclBackend(FakeRawDebugger())
    capabilities = backend.capabilities()
    assert capabilities.backend == "pyrcl"
    assert capabilities.supports("register.read") is True
    assert capabilities.supports("practice.arguments") is True
    assert capabilities.supports("direct_access") is True
    assert capabilities.breakpoint["type"] == ["PROGRAM", "READ", "WRITE", "RW"]


def test_layer0_practice_accepts_arguments_and_timeout():
    raw = FakeRawDebugger()
    backend = PyrclBackend(raw)
    backend.practice_run("scripts/init board.cmm", arguments=("cpu0", "hello world"), timeout=2.0)
    assert raw.cmm_calls == [('"scripts/init board.cmm" cpu0 "hello world"', 2.0)]


def test_layer0_normalizes_register_not_found_error():
    class RegisterNotFoundError(Exception):
        pass

    raw = FakeRawDebugger()
    raw.register = SimpleNamespace(read=lambda _name: (_ for _ in ()).throw(RegisterNotFoundError("missing")))
    with pytest.raises(Trace32BackendError) as caught:
        PyrclBackend(raw).register_read("TTBR0_EL1")
    assert caught.value.code is BackendErrorCode.REGISTER_NOT_FOUND
    assert caught.value.operation == "register.read"


def test_layer0_f32_uses_pyrcl_float_methods():
    calls = []

    class MemoryService:
        def read_float(self, address, **kwargs):
            calls.append(("read_float", address, kwargs))
            return 1.5

        def write_float(self, address, value, **kwargs):
            calls.append(("write_float", address, value, kwargs))

    raw = FakeRawDebugger()
    raw.memory = MemoryService()
    backend = PyrclBackend(raw)

    assert backend.memory_read_typed("VM:0x1000", type_name="f32") == 1.5
    backend.memory_write_typed("VM:0x1000", 2.5, type_name="f32")

    assert calls == [
        ("read_float", "VM:0x1000", {}),
        ("write_float", "VM:0x1000", 2.5, {}),
    ]


class FakeBackend:
    def __init__(self):
        self.commands = []
        self.functions = []
        self.breakpoint_entries = []

    def command(self, command):
        self.commands.append(command)

    def function(self, expression):
        self.functions.append(expression)
        mapping = {
            "STATE.RUN()": False,
            "PP()": 0x1000,
            "Var.VALUE(foo)": 7,
            "Var.TYPEOF(foo)": "unsigned int",
            "Var.ADDRESS(foo)": "D:0x2000",
            "Var.SIZEOF(foo)": 4,
            "TASK.COUNT()": 2,
            "TASK.FIRST()": 0x10,
            "TASK.NAME(0x10)": "idle",
            'TASK.ID("idle")': 1,
            'TASK.SPACEID("idle")': 0x100,
            "TASK.NEXT(0x10)": 0x20,
            "TASK.NAME(0x20)": "worker",
            'TASK.ID("worker")': 2,
            'TASK.SPACEID("worker")': 0x200,
            "TASK.NEXT(0x20)": 0,
            "TASK.CURRENT.TASK()": 0x20,
            "TASK.CURRENT.TASKNAME()": "worker",
            "TASK.CURRENT.SPACEID()": 0x200,
            "TASK.CURRENT.MACHINEID()": 0,
            "CORE()": 0,
        }
        if expression.startswith("sYmbol.SOURCEFILE"):
            return "main.c"
        if expression.startswith("sYmbol.SOURCELINE"):
            return 10
        if expression.startswith("sYmbol.FUNCTION"):
            return "main"
        if expression.startswith("DISASSEMBLE.ADDRESS"):
            return "NOP"
        return mapping[expression]

    def capabilities(self):
        return SimpleNamespace(backend="fake")

    def breakpoint_parameters(self):
        return {"type": ["PROGRAM"], "implementation": ["AUTO"], "action": ["STOP"]}

    def breakpoint_list(self):
        return self.breakpoint_entries

    def address_parse(self, text):
        return SimpleNamespace(value=int(str(text).split(":")[-1], 0), access=None)

    def address_create(self, *, access, value):
        return SimpleNamespace(value=value, access=access)

    def symbol_query_by_address(self, _address):
        return SimpleNamespace(name="main")


def test_layer1_stop_reason_infers_only_exact_program_breakpoint():
    backend = FakeBackend()
    backend.breakpoint_entries = [
        SimpleNamespace(
            enabled=True,
            type_=SimpleNamespace(name="PROGRAM"),
            address=SimpleNamespace(value=0x1000),
        )
    ]
    event = Debugger(backend).current_stop_event()
    assert event.reason is StopReason.BREAKPOINT
    assert event.breakpoint_id == 0
    assert event.reason_source == "breakpoint-pc-match"
    assert event.confidence == "inferred"


def test_layer1_expression_result_contains_type_address_and_size():
    result = Debugger(FakeBackend()).expression_evaluate("foo")
    assert result.value == 7
    assert result.type_name == "unsigned int"
    assert result.address == "D:0x2000"
    assert result.size == 4


def test_layer1_task_context_is_generic_os_awareness():
    debugger = Debugger(FakeBackend())
    current = debugger.task_current()
    tasks = debugger.task_list()
    assert current is not None and current.name == "worker"
    assert [task.name for task in tasks] == ["idle", "worker"]
    assert tasks[1].current is True


def test_completed_schema_and_capabilities_are_local(capsys):
    parser = build_parser()
    commands = parser.parse_args(["backend", "capabilities"])
    assert commands.command_name == "backend capabilities"

    assert main(["--json", "capabilities"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert "core_completion" in data["debugger_model"]
    assert "REGISTER_NOT_FOUND" in data["errors"]["stable_layer0_codes"]

    assert main(["--json", "schema"]) == 0
    schema = json.loads(capsys.readouterr().out)["data"]["commands"]
    assert "backend capabilities" in schema
    assert "context task-list" in schema
    assert "frame current" in schema
    assert "frame select" in schema
    practice_flags = {
        flag
        for argument in schema["practice run"]["arguments"]
        for flag in argument.get("flags", [])
    }
    assert "--timeout" in practice_flags
