from types import SimpleNamespace

import pytest

from trace32_cli import selftest
from trace32_cli.entry import build_parser


def test_test_plans_are_explicit_and_skip_vm_is_removed():
    parser = build_parser()

    assert parser.parse_args(["test"]).test_plan == "read-only"
    assert parser.parse_args(["test", "--memory"]).test_plan == "memory"
    assert parser.parse_args(["test", "--extended"]).test_plan == "extended"
    assert parser.parse_args(["test", "--execution"]).test_plan == "execution"
    assert parser.parse_args(["test", "--all"]).test_plan == "all"

    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["test", "--skip-vm"])
    assert caught.value.code == 2


def test_test_plans_are_cumulative_and_all_tracks_registered_suites():
    assert selftest.get_plan("read-only").includes(selftest.SUITE_MEMORY) is False
    assert selftest.get_plan("memory").includes(selftest.SUITE_MEMORY) is True
    assert selftest.get_plan("extended").includes(selftest.SUITE_MEMORY) is True
    assert selftest.get_plan("extended").includes(selftest.SUITE_EXTENDED) is True
    assert selftest.get_plan("execution").includes(selftest.SUITE_EXECUTION) is True
    assert selftest.get_plan("all").suites == frozenset(selftest.OPTIONAL_SUITES)


def test_breakpoint_lifecycle_uses_object_methods_and_cleans_up():
    class Address:
        access = "P"
        value = 0x1000

    class AddressService:
        def from_string(self, _text):
            return Address()

    class Breakpoint:
        def __init__(self):
            self.enabled = True
            self.deleted = False

        def disable(self):
            self.enabled = False

        def enable(self):
            self.enabled = True

        def delete(self):
            self.deleted = True

    bp = Breakpoint()

    class BreakpointService:
        def __init__(self):
            self.items = []

        def list(self):
            return [item for item in self.items if not item.deleted]

        def set(self, *, address, core=None):
            assert address.value == 0x1000
            assert core == 0
            self.items.append(bp)
            return bp

    service = BreakpointService()
    dbg = SimpleNamespace(address=AddressService(), breakpoint=service)
    result = selftest._breakpoint_lifecycle(dbg, "P:0x1000", 0)

    assert result["before"] == 0
    assert result["after"] == 0
    assert bp.deleted is True
    assert bp.enabled is True


def test_execution_sequence_restores_running_state_mode():
    class Debugger:
        def __init__(self):
            self.running = True
            self.commands = []

        def fnc(self, expression):
            assert expression == "STATE.RUN()"
            return self.running

        def cmd(self, command):
            self.commands.append(command)
            if command == "Break":
                self.running = False
            elif command == "Go":
                self.running = True
            elif command == "Step":
                self.running = False

    dbg = Debugger()
    cases = []
    result = selftest._run_execution_tests(dbg, cases)

    assert result["initial_running"] is True
    assert result["final_running"] is True
    assert dbg.commands == ["Break", "Step", "Go"]
    assert [case["id"] for case in cases] == [
        "execution.halt",
        "execution.step",
        "execution.run",
        "execution.restore_state",
    ]
    assert all(case["status"] == "pass" for case in cases)


def test_execution_sequence_restores_halted_state_mode():
    class Debugger:
        def __init__(self):
            self.running = False
            self.commands = []

        def fnc(self, expression):
            assert expression == "STATE.RUN()"
            return self.running

        def cmd(self, command):
            self.commands.append(command)
            if command == "Break":
                self.running = False
            elif command == "Go":
                self.running = True
            elif command == "Step":
                self.running = False

    dbg = Debugger()
    cases = []
    result = selftest._run_execution_tests(dbg, cases)

    assert result["initial_running"] is False
    assert result["final_running"] is False
    assert dbg.commands == ["Break", "Step", "Go", "Break"]
    assert cases[-1]["id"] == "execution.restore_state"
    assert cases[-1]["status"] == "pass"
