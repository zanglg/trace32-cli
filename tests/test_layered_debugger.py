from __future__ import annotations

from types import SimpleNamespace

import pytest

from trace32_cli.layer0 import PyrclBackend
from trace32_cli.layer1 import (
    AddressLocation,
    DebugContext,
    Debugger,
    ExecutionState,
    SourceLocation,
    StopReason,
    SymbolLocation,
)


class FakeBackend:
    def __init__(self):
        self.commands = []
        self.functions = []
        self.register_reads = []
        self.register_writes = []
        self.states = [False]
        self.addresses = {}

    def command(self, command):
        self.commands.append(command)

    def function(self, function):
        self.functions.append(function)
        if function == "PP()":
            return 0x1000
        if function.startswith("sYmbol.SOURCEFILE"):
            return "main.c"
        if function.startswith("sYmbol.SOURCELINE"):
            return 42
        if function.startswith("sYmbol.FUNCTION"):
            return "main"
        if function.startswith("DISASSEMBLE.ADDRESS"):
            return "NOP"
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]

    def address_parse(self, text):
        return SimpleNamespace(access=None, value=int(str(text).split(":")[-1], 0), text=text)

    def address_create(self, *, access, value):
        return SimpleNamespace(access=access, value=value)

    def register_read(self, name, *, core=None):
        self.register_reads.append((name, core))
        return {"name": name, "core": core, "value": 0x1234}

    def register_write(self, name, value, *, core=None):
        self.register_writes.append((name, value, core))

    def register_read_many(self, names, *, core=None):
        return [self.register_read(name, core=core) for name in names]

    def register_list(self, *, core=None, unit=None):
        return []

    def memory_read(self, address, *, length):
        return bytes(range(length))

    def memory_write(self, address, data):
        self.last_memory_write = (address, data)

    def memory_read_typed(self, address, *, type_name, byteorder=None):
        return address.value

    def memory_write_typed(self, address, value, *, type_name, byteorder=None):
        self.last_typed_write = (address.value, value, type_name, byteorder)

    def breakpoint_set(self, **kwargs):
        self.last_breakpoint = kwargs
        return kwargs

    def breakpoint_list(self):
        return []

    def breakpoint_delete(self, index):
        return None

    def breakpoint_enable(self, index):
        return None

    def breakpoint_disable(self, index):
        return None

    def breakpoint_clear(self):
        return 0

    def symbol_query_by_name(self, name):
        return SimpleNamespace(name=name, address=SimpleNamespace(value=0x2000))

    def symbol_query_by_address(self, address):
        return SimpleNamespace(name="main", address=address)

    def variable_read(self, name):
        return SimpleNamespace(value=1)

    def variable_write(self, name, value):
        return None

    def practice_run(self, command, *, timeout=None):
        return None

    def macro_get(self, name):
        return None

    def macro_set(self, name, value):
        return None

    def direct_access(self):
        return None


def test_layer1_register_name_is_opaque_and_passed_through():
    backend = FakeBackend()
    debugger = Debugger(backend)
    result = debugger.register_read("TTBR0_EL1")
    assert result["value"] == 0x1234
    assert backend.register_reads == [("TTBR0_EL1", None)]


def test_layer1_register_context_passes_core_without_architecture_logic():
    backend = FakeBackend()
    Debugger(backend).register_read("mstatus", context=DebugContext(core=2))
    assert backend.register_reads == [("mstatus", 2)]


def test_layer1_execution_distinguishes_instruction_and_source_steps():
    backend = FakeBackend()
    debugger = Debugger(backend)
    assert debugger.continue_execution() is ExecutionState.RUNNING
    halted = debugger.halt()
    instruction = debugger.step_instruction()
    source = debugger.step_source()
    debugger.next()
    debugger.finish()
    assert backend.commands == [
        "Go",
        "Break",
        "Step.Asm",
        "Step.Hll",
        "Step.Over",
        "Step.Return",
    ]
    assert halted.reason is StopReason.HALT
    assert instruction.reason is StopReason.STEP
    assert source.reason is StopReason.STEP


def test_layer1_wait_polls_state_until_stopped():
    backend = FakeBackend()
    backend.states = [True, True, False]
    event = Debugger(backend).wait(timeout=1.0, poll_interval=0.001)
    assert event.state is ExecutionState.STOPPED
    assert backend.functions.count("STATE.RUN()") >= 3


def test_layer1_wait_rejects_invalid_poll_interval():
    with pytest.raises(ValueError, match="poll_interval"):
        Debugger(FakeBackend()).wait(poll_interval=0)


def test_layer1_location_model_supports_address_symbol_and_source():
    backend = FakeBackend()
    debugger = Debugger(backend)
    assert debugger.location_expression(AddressLocation("0x1000")) == "0x1000"
    assert debugger.location_expression(SymbolLocation("main")) == "main"
    assert debugger.location_expression(SourceLocation("main.c", 12)).endswith("\\12")


def test_layer1_typed_memory_offsets_without_architecture_knowledge():
    backend = FakeBackend()
    debugger = Debugger(backend)
    _address, values = debugger.memory_read_typed("0x1000", type_name="u32", count=2)
    assert values == [0x1000, 0x1004]


def test_layer1_disassembly_and_source_are_generic_semantics():
    backend = FakeBackend()
    debugger = Debugger(backend)
    source = debugger.source_current()
    instruction = debugger.instruction_disassemble(AddressLocation("0x1000"))
    assert source.function == "main"
    assert source.file == "main.c"
    assert instruction.text == "NOP"


class FakeRegisterService:
    def __init__(self):
        self.calls = []

    def read(self, name, **kwargs):
        self.calls.append(("read", name, kwargs))
        return SimpleNamespace(name=name, value=7)

    def write(self, name, value, **kwargs):
        self.calls.append(("write", name, value, kwargs))

    def read_all(self, **kwargs):
        self.calls.append(("read_all", kwargs))
        return []


class FakePyrclDebugger:
    def __init__(self):
        self.register = FakeRegisterService()
        self.memory = SimpleNamespace()
        self.address = SimpleNamespace()


def test_layer0_pyrcl_register_adapter_preserves_register_name():
    raw = FakePyrclDebugger()
    backend = PyrclBackend(raw)
    result = backend.register_read("ESR_EL1", core=1)
    backend.register_write("mcause", 9)
    assert result.value == 7
    assert raw.register.calls == [
        ("read", "ESR_EL1", {"core": 1}),
        ("write", "mcause", 9, {}),
    ]
