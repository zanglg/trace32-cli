"""Architecture-neutral debugger models for Layer 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Union


class ExecutionState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class StopReason(str, Enum):
    BREAKPOINT = "breakpoint"
    WATCHPOINT = "watchpoint"
    STEP = "step"
    HALT = "halt"
    EXCEPTION = "exception"
    EXITED = "exited"
    UNKNOWN = "unknown"


class WatchAccess(str, Enum):
    READ = "read"
    WRITE = "write"
    ACCESS = "access"


@dataclass(frozen=True)
class AddressLocation:
    address: str


@dataclass(frozen=True)
class SymbolLocation:
    symbol: str


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int


Location = Union[AddressLocation, SymbolLocation, SourceLocation]


@dataclass(frozen=True)
class DebugContext:
    """Optional execution context selectors.

    Not every target has every context level. Bare-metal targets may only use
    ``core`` while OS-aware targets can add machine/process/task/frame selectors.
    """

    core: int | None = None
    machine: int | None = None
    process: int | str | None = None
    thread: int | str | None = None
    task: int | str | None = None
    frame: int | None = None


@dataclass(frozen=True)
class StopEvent:
    state: ExecutionState
    reason: StopReason = StopReason.UNKNOWN
    pc: int | str | None = None
    breakpoint_id: int | str | None = None
    detail: str | None = None
    reason_source: str | None = None
    confidence: str = "unknown"


@dataclass(frozen=True)
class SourceInfo:
    address: object | None = None
    file: str | None = None
    line: int | None = None
    function: str | None = None


@dataclass(frozen=True)
class ResolvedLocation:
    kind: str
    expression: str
    address: object | None = None
    symbol: str | None = None
    source: SourceInfo | None = None


@dataclass(frozen=True)
class ExpressionResult:
    expression: str
    value: Any
    type_name: str | None = None
    address: object | None = None
    size: int | None = None


@dataclass(frozen=True)
class TypeInfo:
    expression: str
    name: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class Instruction:
    address: object
    text: str
    symbol: str | None = None
    source: SourceInfo | None = None


@dataclass(frozen=True)
class StackFrame:
    level: int
    address: object | None = None
    function: str | None = None
    file: str | None = None
    line: int | None = None
    selected: bool = False


@dataclass(frozen=True)
class TaskInfo:
    magic: int | str
    name: str | None = None
    task_id: int | str | None = None
    space_id: int | str | None = None
    current: bool = False
