"""Generic debugger operations built on the Layer 0 TRACE32 backend."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

from trace32_cli.layer0 import Trace32Backend

from .models import (
    AddressLocation,
    DebugContext,
    ExecutionState,
    Instruction,
    Location,
    SourceInfo,
    SourceLocation,
    StackFrame,
    StopEvent,
    StopReason,
    SymbolLocation,
    WatchAccess,
)

_TYPE_WIDTH = {
    "u8": 1,
    "s8": 1,
    "u16": 2,
    "s16": 2,
    "u32": 4,
    "s32": 4,
    "u64": 8,
    "s64": 8,
    "f32": 4,
    "f64": 8,
}


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _as_bool(value: Any) -> bool | None:
    value = _value(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1", "running", "run"}:
            return True
        if normalized in {"false", "no", "off", "0", "stopped", "halted", "halt"}:
            return False
    return None


def _execution_state(value: Any) -> ExecutionState:
    parsed = _as_bool(value)
    if parsed is True:
        return ExecutionState.RUNNING
    if parsed is False:
        return ExecutionState.STOPPED
    text = str(_value(value)).strip().lower()
    if "running" in text:
        return ExecutionState.RUNNING
    if any(token in text for token in ("stopped", "halted", "break")):
        return ExecutionState.STOPPED
    return ExecutionState.UNKNOWN


def _architecture(cpu_family: Any, is_64bit: Any, arm64: Any) -> str | None:
    family = str(_value(cpu_family)).strip() if cpu_family not in (None, "") else ""
    upper = family.upper()
    is64 = _as_bool(is_64bit)
    arm64_value = _as_bool(arm64)
    if upper == "ARM" and arm64_value is True:
        return "AArch64"
    if upper == "ARM":
        return "ARM64" if is64 else "ARM"
    if "RISCV" in upper or "RISC-V" in upper:
        return "RISC-V64" if is64 else "RISC-V"
    return family or None


def _quote(text: str) -> str:
    return '"' + text.replace('"', '\\"') + '"'


def _source_expression(location: SourceLocation) -> str:
    return f"{_quote(location.file)}\\{location.line}"


class Debugger:
    """Architecture-neutral debugger facade.

    The facade models GDB-inspired debugger semantics while leaving TRACE32
    mechanisms in Layer 0. Architecture-specific register names stay opaque.
    """

    def __init__(self, backend: Trace32Backend):
        self.backend = backend

    def target_attach(self) -> None:
        self.backend.command("SYStem.Attach")

    def target_detach(self) -> None:
        self.backend.command("SYStem.Down")

    def target_up(self) -> None:
        self.backend.command("SYStem.Up")

    def target_reset(self) -> None:
        self.backend.command("SYStem.RESetTarget")

    def target_info(self) -> dict[str, Any]:
        unavailable: dict[str, str] = {}

        def optional(expression: str) -> Any:
            try:
                return _value(self.backend.function(expression))
            except Exception as exc:
                unavailable[expression] = str(exc)
                return None

        cpu = optional("CPU()")
        cpu_family = optional("CPUFAMILY()")
        core_version = optional("CPUCOREVERSION()")
        is_64bit = optional("CPUIS64BIT()")
        configured_cores = optional("CONFIGNUMBER()")
        big_endian = optional("SYStem.BIGENDIAN()")
        running = optional("STATE.RUN()")
        halted = optional("STATE.HALT()")
        target_state = optional("STATE.TARGET()")
        selected_core = optional("CORE()")

        arm64 = None
        if str(cpu_family).strip().upper() == "ARM":
            arm64 = optional("ARM64()")

        state = ExecutionState.UNKNOWN.value
        if _as_bool(running) is True:
            state = ExecutionState.RUNNING.value
        elif _as_bool(halted) is True:
            state = "halted"

        endian = None
        big_endian_bool = _as_bool(big_endian)
        if big_endian_bool is not None:
            endian = "big" if big_endian_bool else "little"

        result = {
            "cpu": cpu,
            "cpu_family": cpu_family,
            "core_version": core_version,
            "architecture": _architecture(cpu_family, is_64bit, arm64),
            "is_64bit": _as_bool(is_64bit),
            "configured_cores": configured_cores,
            "selected_core": selected_core,
            "state": state,
            "target_state": target_state,
            "endianness": endian,
        }
        if arm64 is not None:
            result["arm64"] = _as_bool(arm64)
        if unavailable:
            result["unavailable"] = unavailable
        return result

    def state(self) -> ExecutionState:
        try:
            value = self.backend.function("STATE.RUN()")
        except Exception:
            value = self.backend.function("STATE()")
        return _execution_state(value)

    def continue_execution(self) -> ExecutionState:
        self.backend.command("Go")
        return ExecutionState.RUNNING

    def run_to(self, location: Location) -> ExecutionState:
        self.backend.command(f"Go {self.location_expression(location)}")
        return ExecutionState.RUNNING

    def halt(self) -> StopEvent:
        self.backend.command("Break")
        return self.current_stop_event(reason=StopReason.HALT)

    def step(self) -> StopEvent:
        self.backend.command("Step")
        return self.current_stop_event(reason=StopReason.STEP)

    def step_instruction(self) -> StopEvent:
        self.backend.command("Step.Asm")
        return self.current_stop_event(reason=StopReason.STEP)

    def step_source(self) -> StopEvent:
        self.backend.command("Step.Hll")
        return self.current_stop_event(reason=StopReason.STEP)

    def next(self) -> StopEvent:
        self.backend.command("Step.Over")
        return self.current_stop_event(reason=StopReason.STEP)

    def finish(self) -> StopEvent:
        self.backend.command("Step.Return")
        return self.current_stop_event(reason=StopReason.STEP)

    def current_stop_event(self, *, reason: StopReason = StopReason.UNKNOWN) -> StopEvent:
        state = self.state()
        pc: Any = None
        try:
            pc = _value(self.backend.function("PP()"))
        except Exception:
            pass
        return StopEvent(state=state, reason=reason, pc=pc)

    def wait(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.05,
    ) -> StopEvent:
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be >= 0")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be > 0")

        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            state = self.state()
            if state is not ExecutionState.RUNNING:
                event = self.current_stop_event()
                return StopEvent(
                    state=event.state,
                    reason=StopReason.UNKNOWN,
                    pc=event.pc,
                )
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("target did not stop before timeout")
            time.sleep(poll_interval)

    def context_current(self) -> dict[str, Any]:
        core = None
        try:
            core = _value(self.backend.function("CORE()"))
        except Exception:
            pass
        source = self.source_current()
        return {
            "core": core,
            "process": None,
            "thread": None,
            "frame": 0,
            "source": source,
        }

    def register_read(self, name: str, *, context: DebugContext | None = None) -> Any:
        core = context.core if context is not None else None
        return self.backend.register_read(name, core=core)

    def register_write(
        self,
        name: str,
        value: int,
        *,
        context: DebugContext | None = None,
    ) -> Any:
        core = context.core if context is not None else None
        return self.backend.register_write(name, value, core=core)

    def register_read_many(
        self,
        names: Iterable[str],
        *,
        context: DebugContext | None = None,
    ) -> list[Any]:
        core = context.core if context is not None else None
        return self.backend.register_read_many(list(names), core=core)

    def register_list(
        self,
        *,
        context: DebugContext | None = None,
        unit: str | None = "CPU",
    ) -> list[Any]:
        core = context.core if context is not None else None
        return self.backend.register_list(core=core, unit=unit)

    def address_parse(self, text: str, *, access: str | None = None) -> Any:
        value = text if ":" in text or not access else f"{access}:{text}"
        return self.backend.address_parse(value)

    def _offset_address(self, address: Any, offset: int) -> Any:
        if offset == 0:
            return address
        value = getattr(address, "value", None)
        if value is None:
            raise ValueError("address object has no numeric value for offset access")
        return self.backend.address_create(access=getattr(address, "access", None), value=value + offset)

    def memory_read_typed(
        self,
        address: str,
        *,
        type_name: str = "u8",
        count: int = 1,
        byteorder: str | None = None,
        access: str | None = None,
    ) -> tuple[Any, list[Any]]:
        if type_name not in _TYPE_WIDTH:
            raise ValueError(f"unsupported memory type: {type_name}")
        if count < 1:
            raise ValueError("count must be >= 1")
        addr = self.address_parse(address, access=access)
        width = _TYPE_WIDTH[type_name]
        values = [
            self.backend.memory_read_typed(
                self._offset_address(addr, index * width),
                type_name=type_name,
                byteorder=byteorder,
            )
            for index in range(count)
        ]
        return addr, values

    def memory_write_typed(
        self,
        address: str,
        values: Iterable[int | float],
        *,
        type_name: str = "u8",
        byteorder: str | None = None,
        access: str | None = None,
    ) -> tuple[Any, list[int | float]]:
        if type_name not in _TYPE_WIDTH:
            raise ValueError(f"unsupported memory type: {type_name}")
        addr = self.address_parse(address, access=access)
        width = _TYPE_WIDTH[type_name]
        materialized = list(values)
        for index, value in enumerate(materialized):
            self.backend.memory_write_typed(
                self._offset_address(addr, index * width),
                value,
                type_name=type_name,
                byteorder=byteorder,
            )
        return addr, materialized

    def memory_dump(
        self,
        address: str,
        *,
        length: int,
        access: str | None = None,
    ) -> tuple[Any, bytes]:
        if length < 0:
            raise ValueError("length must be >= 0")
        addr = self.address_parse(address, access=access)
        return addr, self.backend.memory_read(addr, length=length)

    def memory_write_bytes(
        self,
        address: str,
        data: bytes,
        *,
        access: str | None = None,
    ) -> Any:
        addr = self.address_parse(address, access=access)
        self.backend.memory_write(addr, data)
        return addr

    def memory_search(
        self,
        address: str,
        *,
        length: int,
        pattern: bytes,
        access: str | None = None,
    ) -> list[int]:
        if not pattern:
            raise ValueError("pattern must not be empty")
        addr, data = self.memory_dump(address, length=length, access=access)
        base = getattr(addr, "value", None)
        if base is None:
            raise ValueError("address object has no numeric value for search result offsets")
        hits: list[int] = []
        start = 0
        while True:
            index = data.find(pattern, start)
            if index < 0:
                break
            hits.append(base + index)
            start = index + 1
        return hits

    def memory_compare(
        self,
        address: str,
        expected: bytes,
        *,
        access: str | None = None,
    ) -> dict[str, Any]:
        _, actual = self.memory_dump(address, length=len(expected), access=access)
        mismatches = [
            {"offset": index, "expected": wanted, "actual": got}
            for index, (wanted, got) in enumerate(zip(expected, actual))
            if wanted != got
        ]
        return {"equal": not mismatches, "mismatches": mismatches, "actual": actual}

    def memory_fill(
        self,
        address: str,
        *,
        length: int,
        pattern: bytes,
        access: str | None = None,
    ) -> Any:
        if length < 0:
            raise ValueError("length must be >= 0")
        if not pattern:
            raise ValueError("pattern must not be empty")
        data = (pattern * ((length + len(pattern) - 1) // len(pattern)))[:length]
        return self.memory_write_bytes(address, data, access=access)

    def location_expression(self, location: Location) -> str:
        if isinstance(location, AddressLocation):
            return location.address
        if isinstance(location, SymbolLocation):
            return location.symbol
        if isinstance(location, SourceLocation):
            return _source_expression(location)
        raise TypeError(f"unsupported location: {type(location)!r}")

    def _location_address(self, location: Location) -> Any:
        if isinstance(location, AddressLocation):
            return self.address_parse(location.address)
        if isinstance(location, SymbolLocation):
            symbol = self.backend.symbol_query_by_name(location.symbol)
            address = getattr(symbol, "address", None)
            if address is None:
                raise ValueError(f"symbol has no address: {location.symbol}")
            return address
        if isinstance(location, SourceLocation):
            try:
                return self.backend.function(f"sYmbol.BEGIN({_source_expression(location)})")
            except Exception as exc:
                raise ValueError(
                    "source location cannot be resolved to an address by this TRACE32 configuration"
                ) from exc
        raise TypeError(f"unsupported location: {type(location)!r}")

    def breakpoint_set(
        self,
        location: Location,
        *,
        core: int | None = None,
        size: int | None = None,
        implementation: str | None = None,
        action: str | None = None,
    ) -> Any:
        if isinstance(location, SourceLocation):
            self.backend.command(f"Break.Set {self.location_expression(location)}")
            entries = self.backend.breakpoint_list()
            return entries[-1] if entries else None
        address = self._location_address(location)
        return self.backend.breakpoint_set(
            address=address,
            size=size,
            type_name="PROGRAM",
            impl_name=implementation,
            action_name=action,
            core=core,
        )

    def watchpoint_set(
        self,
        location: Location,
        *,
        access: WatchAccess,
        core: int | None = None,
        size: int | None = None,
        implementation: str | None = None,
    ) -> Any:
        type_name = {
            WatchAccess.READ: "READ",
            WatchAccess.WRITE: "WRITE",
            WatchAccess.ACCESS: "RW",
        }[access]
        return self.backend.breakpoint_set(
            address=self._location_address(location),
            size=size,
            type_name=type_name,
            impl_name=implementation,
            core=core,
        )

    def breakpoint_list(self) -> list[Any]:
        return self.backend.breakpoint_list()

    def breakpoint_delete(self, index: int) -> Any:
        return self.backend.breakpoint_delete(index)

    def breakpoint_enable(self, index: int) -> Any:
        return self.backend.breakpoint_enable(index)

    def breakpoint_disable(self, index: int) -> Any:
        return self.backend.breakpoint_disable(index)

    def breakpoint_clear(self) -> int:
        return self.backend.breakpoint_clear()

    def symbol_by_name(self, name: str) -> Any:
        return self.backend.symbol_query_by_name(name)

    def symbol_by_address(self, address: str, *, access: str | None = None) -> Any:
        return self.backend.symbol_query_by_address(self.address_parse(address, access=access))

    def variable_read(self, name: str) -> Any:
        return self.backend.variable_read(name)

    def variable_write(self, name: str, value: Any) -> Any:
        return self.backend.variable_write(name, value)

    def expression_evaluate(self, expression: str) -> Any:
        return _value(self.backend.function(f"Var.VALUE({expression})"))

    def expression_assign(self, expression: str, value: str) -> Any:
        return self.backend.command(f"Var.Assign {expression}={value}")

    def type_describe(self, expression: str) -> Any:
        return _value(self.backend.function(f"Var.TYPEOF({expression})"))

    def _source_for_address(self, address: Any) -> SourceInfo:
        file_name = None
        line = None
        function = None
        try:
            file_name = _value(self.backend.function(f"sYmbol.SOURCEFILE({address})"))
        except Exception:
            pass
        try:
            line_value = _value(self.backend.function(f"sYmbol.SOURCELINE({address})"))
            line = int(line_value) if line_value not in (None, "") else None
        except Exception:
            pass
        try:
            function = _value(self.backend.function(f"sYmbol.FUNCTION({address})"))
        except Exception:
            pass
        return SourceInfo(address=address, file=file_name or None, line=line, function=function or None)

    def source_current(self) -> SourceInfo:
        try:
            address = _value(self.backend.function("PP()"))
        except Exception:
            address = None
        if address is None:
            return SourceInfo()
        return self._source_for_address(address)

    def source_resolve(self, location: Location) -> SourceInfo:
        if isinstance(location, SourceLocation):
            address = None
            try:
                address = _value(self._location_address(location))
            except Exception:
                pass
            return SourceInfo(address=address, file=location.file, line=location.line)
        return self._source_for_address(self._location_address(location))

    def source_list(self, *, limit: int = 1024) -> list[str]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        files: list[str] = []
        expression = "sYmbol.LIST.SOURCE(1,1,1)"
        for index in range(limit):
            value = _value(self.backend.function(expression))
            text = str(value).strip() if value is not None else ""
            if not text or text in files:
                break
            files.append(text)
            expression = "sYmbol.LIST.SOURCE(0,1,0)"
            if index + 1 == limit:
                break
        return files

    def instruction_disassemble(self, location: Location | None = None) -> Instruction:
        address: Any
        if location is None:
            address = _value(self.backend.function("PP()"))
        else:
            address = self._location_address(location)
        text = _value(self.backend.function(f"DISASSEMBLE.ADDRESS({address})"))
        return Instruction(address=address, text=str(text))

    def stack_backtrace(self, *, max_frames: int = 64) -> list[StackFrame]:
        if max_frames < 1:
            raise ValueError("max_frames must be >= 1")

        frames: list[StackFrame] = []
        moved = 0
        source = self.source_current()
        try:
            for level in range(max_frames):
                frames.append(
                    StackFrame(
                        level=level,
                        address=source.address,
                        function=source.function,
                        file=source.file,
                        line=source.line,
                    )
                )
                if level + 1 >= max_frames:
                    break
                current = (source.address, source.function, source.file, source.line)
                try:
                    self.backend.command("Frame.Up")
                    next_source = self.source_current()
                except Exception:
                    break
                next_fingerprint = (
                    next_source.address,
                    next_source.function,
                    next_source.file,
                    next_source.line,
                )
                if next_fingerprint == current:
                    break
                moved += 1
                source = next_source
        finally:
            for _ in range(moved):
                try:
                    self.backend.command("Frame.Down")
                except Exception:
                    break
        return frames

    def frame_up(self) -> SourceInfo:
        self.backend.command("Frame.Up")
        return self.source_current()

    def frame_down(self) -> SourceInfo:
        self.backend.command("Frame.Down")
        return self.source_current()

    def program_list(self, *, limit: int = 256) -> list[str]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        programs: list[str] = []
        expression = "sYmbol.LIST.PROGRAM(1)"
        for _ in range(limit):
            value = _value(self.backend.function(expression))
            text = str(value).strip() if value is not None else ""
            if not text or text in programs:
                break
            programs.append(text)
            expression = "sYmbol.LIST.PROGRAM(0)"
        return programs

    def program_load_elf(self, path: str, *, symbols_only: bool = False) -> None:
        command = f"Data.LOAD.Elf {_quote(str(Path(path)))}"
        if symbols_only:
            command += " /NoCODE"
        self.backend.command(command)

    def program_load_binary(self, path: str, address: str) -> None:
        self.backend.command(f"Data.LOAD.Binary {_quote(str(Path(path)))} {address}")

    def practice_run(self, command: str, *, timeout: float | None = None) -> Any:
        return self.backend.practice_run(command, timeout=timeout)

    def macro_get(self, name: str) -> Any:
        return self.backend.macro_get(name)

    def macro_set(self, name: str, value: str) -> Any:
        return self.backend.macro_set(name, value)
