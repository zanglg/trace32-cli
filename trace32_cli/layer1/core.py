"""Completed generic debugger semantics layered on the initial debugger facade."""

from __future__ import annotations

import time
from typing import Any

from trace32_cli.layer0 import BackendErrorCode, Trace32BackendError

from .debugger import Debugger as _BaseDebugger
from .debugger import _quote, _value
from .models import (
    AddressLocation,
    ExpressionResult,
    Instruction,
    Location,
    ResolvedLocation,
    SourceInfo,
    StackFrame,
    StopEvent,
    StopReason,
    TaskInfo,
    TypeInfo,
)


def _address_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", str(value)).upper()


def _fingerprint(source: SourceInfo) -> tuple[Any, ...]:
    return (source.address, source.function, source.file, source.line)


class Debugger(_BaseDebugger):
    """Generic Layer 1 debugger API with normalized results and context."""

    def backend_capabilities(self):
        return self.backend.capabilities()

    def breakpoint_parameters(self) -> dict[str, list[str]]:
        return self.backend.breakpoint_parameters()

    def _classify_breakpoint_stop(self, pc: Any) -> tuple[StopReason, int | None, str, str]:
        pc_value = _address_value(pc)
        try:
            entries = self.backend.breakpoint_list()
        except Exception:
            return StopReason.UNKNOWN, None, "backend-unavailable", "unknown"

        for index, entry in enumerate(entries):
            if not bool(getattr(entry, "enabled", True)):
                continue
            if _enum_name(getattr(entry, "type_", None)) != "PROGRAM":
                continue
            address = getattr(entry, "address", None)
            if address is not None and _address_value(address) == pc_value:
                return StopReason.BREAKPOINT, index, "breakpoint-pc-match", "inferred"
        return StopReason.UNKNOWN, None, "backend-does-not-expose-stop-reason", "unknown"

    def _event(self, state, *, reason: StopReason = StopReason.UNKNOWN) -> StopEvent:
        pc: Any = None
        try:
            pc = _value(self.backend.function("PP()"))
        except Exception:
            pass

        if reason is not StopReason.UNKNOWN:
            return StopEvent(
                state=state,
                reason=reason,
                pc=pc,
                reason_source="operation",
                confidence="known",
            )
        if getattr(state, "value", state) == "stopped":
            classified, bp_index, source, confidence = self._classify_breakpoint_stop(pc)
            return StopEvent(
                state=state,
                reason=classified,
                pc=pc,
                breakpoint_id=bp_index,
                reason_source=source,
                confidence=confidence,
            )
        return StopEvent(
            state=state,
            reason=StopReason.UNKNOWN,
            pc=pc,
            reason_source="state-only",
            confidence="unknown",
        )

    def current_stop_event(self, *, reason: StopReason = StopReason.UNKNOWN) -> StopEvent:
        return self._event(self.state(), reason=reason)

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
            if getattr(state, "value", state) != "running":
                return self._event(state)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("target did not stop before timeout")
            time.sleep(poll_interval)

    def _optional_function(self, expression: str) -> Any:
        try:
            return _value(self.backend.function(expression))
        except Exception:
            return None

    def frame_current(self, *, max_depth: int = 64) -> StackFrame:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        selected_source = self.source_current()
        level = 0
        moved = 0
        current = selected_source
        try:
            for _ in range(max_depth):
                before = _fingerprint(current)
                try:
                    self.backend.command("Frame.Down")
                    candidate = self.source_current()
                except Exception:
                    break
                if _fingerprint(candidate) == before:
                    break
                moved += 1
                level += 1
                current = candidate
        finally:
            for _ in range(moved):
                self.backend.command("Frame.Up")
        return StackFrame(
            level=level,
            address=selected_source.address,
            function=selected_source.function,
            file=selected_source.file,
            line=selected_source.line,
            selected=True,
        )

    def frame_select(self, level: int, *, max_depth: int = 64) -> StackFrame:
        if level < 0:
            raise ValueError("frame level must be >= 0")
        if max_depth < 1 or level >= max_depth:
            raise ValueError("frame level exceeds selection limit")

        # Normalize selection to the actual innermost frame first.
        current = self.source_current()
        for _ in range(max_depth):
            before = _fingerprint(current)
            try:
                self.backend.command("Frame.Down")
                candidate = self.source_current()
            except Exception:
                break
            if _fingerprint(candidate) == before:
                break
            current = candidate

        for _ in range(level):
            before = _fingerprint(current)
            self.backend.command("Frame.Up")
            candidate = self.source_current()
            if _fingerprint(candidate) == before:
                raise ValueError(f"frame level unavailable: {level}")
            current = candidate

        return StackFrame(
            level=level,
            address=current.address,
            function=current.function,
            file=current.file,
            line=current.line,
            selected=True,
        )

    def task_current(self) -> TaskInfo | None:
        magic = self._optional_function("TASK.CURRENT.TASK()")
        name = self._optional_function("TASK.CURRENT.TASKNAME()")
        if magic is None and not name:
            return None
        task_id = None
        space_id = self._optional_function("TASK.CURRENT.SPACEID()")
        if name:
            task_id = self._optional_function(f"TASK.ID({_quote(str(name))})")
        return TaskInfo(magic=magic if magic is not None else "", name=name or None, task_id=task_id, space_id=space_id, current=True)

    def task_list(self, *, limit: int = 1024) -> list[TaskInfo]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        try:
            count = int(_value(self.backend.function("TASK.COUNT()")))
            magic = _value(self.backend.function("TASK.FIRST()")) if count else None
        except Exception as exc:
            raise Trace32BackendError(
                BackendErrorCode.UNSUPPORTED_OPERATION,
                "OS-awareness task enumeration is unavailable",
                operation="context.task.list",
            ) from exc

        current = self.task_current()
        result: list[TaskInfo] = []
        seen: set[Any] = set()
        for _ in range(min(count, limit)):
            if magic is None or magic in seen:
                break
            seen.add(magic)
            rendered_magic = hex(magic) if isinstance(magic, int) else str(magic)
            name = self._optional_function(f"TASK.NAME({rendered_magic})")
            task_id = self._optional_function(f"TASK.ID({_quote(str(name))})") if name else None
            space_id = self._optional_function(f"TASK.SPACEID({_quote(str(name))})") if name else None
            result.append(
                TaskInfo(
                    magic=magic,
                    name=name or None,
                    task_id=task_id,
                    space_id=space_id,
                    current=bool(current and current.magic == magic),
                )
            )
            magic = self._optional_function(f"TASK.NEXT({rendered_magic})")
        return result

    def task_select(self, selector: int | str) -> TaskInfo:
        if isinstance(selector, int):
            rendered = hex(selector)
        else:
            try:
                rendered = hex(int(selector, 0))
            except ValueError:
                rendered = _quote(selector)
        self.backend.command(f"Frame.TASK {rendered}")
        current = self.task_current()
        if current is not None:
            return current
        return TaskInfo(magic=selector, name=str(selector), current=False)

    def context_current(self) -> dict[str, Any]:
        frame = self.frame_current()
        task = self.task_current()
        return {
            "core": self._optional_function("CORE()"),
            "machine": self._optional_function("TASK.CURRENT.MACHINEID()"),
            "space": self._optional_function("TASK.CURRENT.SPACEID()"),
            "process": None,
            "thread": None,
            "task": task,
            "frame": frame,
            "source": self.source_current(),
        }

    def location_resolve(self, location: Location) -> ResolvedLocation:
        expression = self.location_expression(location)
        address = None
        try:
            address = _value(self._location_address(location))
        except Exception:
            pass
        source = None
        if address is not None:
            try:
                source = self._source_for_address(address)
            except Exception:
                pass
        symbol = None
        try:
            if address is not None:
                result = self.backend.symbol_query_by_address(self.address_parse(str(address)))
                symbol = getattr(result, "name", None)
        except Exception:
            pass
        return ResolvedLocation(
            kind="address" if isinstance(location, AddressLocation) else "symbol" if hasattr(location, "symbol") else "source",
            expression=expression,
            address=address,
            symbol=symbol,
            source=source,
        )

    def source_resolve(self, location: Location) -> ResolvedLocation:
        return self.location_resolve(location)

    def expression_evaluate(self, expression: str) -> ExpressionResult:
        value = _value(self.backend.function(f"Var.VALUE({expression})"))
        type_name = self._optional_function(f"Var.TYPEOF({expression})")
        address = self._optional_function(f"Var.ADDRESS({expression})")
        size = self._optional_function(f"Var.SIZEOF({expression})")
        try:
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            size = None
        return ExpressionResult(
            expression=expression,
            value=value,
            type_name=str(type_name) if type_name not in (None, "") else None,
            address=address,
            size=size,
        )

    def type_describe(self, expression: str) -> TypeInfo:
        type_name = _value(self.backend.function(f"Var.TYPEOF({expression})"))
        size = self._optional_function(f"Var.SIZEOF({expression})")
        try:
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            size = None
        return TypeInfo(expression=expression, name=str(type_name), size=size)

    def instruction_disassemble(self, location: Location | None = None) -> Instruction:
        if location is None:
            address = _value(self.backend.function("PP()"))
        else:
            address = _value(self._location_address(location))
        text = _value(self.backend.function(f"DISASSEMBLE.ADDRESS({address})"))
        source = self._source_for_address(address)
        symbol = source.function
        return Instruction(address=address, text=str(text), symbol=symbol, source=source)

    def practice_run(
        self,
        command: str,
        *,
        arguments=(),
        timeout: float | None = None,
    ) -> Any:
        return self.backend.practice_run(command, arguments=tuple(arguments), timeout=timeout)
