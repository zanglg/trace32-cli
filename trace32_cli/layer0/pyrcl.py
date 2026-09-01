"""PYRCL implementation of the Layer 0 TRACE32 capability contract."""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

from .capabilities import BackendCapabilities
from .errors import BackendErrorCode, Trace32BackendError, normalize_backend_error

_T = TypeVar("_T")

_TYPE_METHODS = {
    "u8": "uint8",
    "s8": "int8",
    "u16": "uint16",
    "s16": "int16",
    "u32": "uint32",
    "s32": "int32",
    "u64": "uint64",
    "s64": "int64",
    "f32": "float",
    "f64": "double",
}

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


def _enum_names(enum_class: Any) -> list[str]:
    return list(getattr(enum_class, "__members__", {}).keys())


def _practice_token(text: str) -> str:
    if text and not any(character.isspace() for character in text) and '"' not in text:
        return text
    return '"' + text.replace('"', '\\"') + '"'


class PyrclBackend:
    """Thin, normalized adapter around a connected PYRCL debugger object.

    PYRCL objects, TRACE32 access classes, and register names are preserved.
    Backend exceptions and breakpoint parameter names are normalized so Layer 1
    does not depend on PYRCL implementation details.
    """

    def __init__(self, debugger: Any):
        self.debugger = debugger

    def _call(self, operation: str, function: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        try:
            return function(*args, **kwargs)
        except Exception as exc:
            raise normalize_backend_error(operation, exc) from exc

    def breakpoint_parameters(self) -> dict[str, list[str]]:
        try:
            prototype = self.debugger.breakpoint()
            return {
                "type": _enum_names(prototype.Type),
                "implementation": _enum_names(prototype.Impl),
                "action": _enum_names(prototype.Action),
            }
        except Exception as exc:
            raise normalize_backend_error("breakpoint.parameters", exc) from exc

    def capabilities(self) -> BackendCapabilities:
        services = {
            name: hasattr(self.debugger, attribute)
            for name, attribute in {
                "address": "address",
                "memory": "memory",
                "register": "register",
                "breakpoint": "breakpoint",
                "symbol": "symbol",
                "variable": "variable",
                "command": "cmd",
                "function": "fnc",
                "practice": "practice",
                "direct_access": "directaccess",
            }.items()
        }
        breakpoint: dict[str, list[str]] = {}
        if services["breakpoint"]:
            try:
                breakpoint = self.breakpoint_parameters()
            except Trace32BackendError:
                breakpoint = {}
        features = {
            "address.parse": services["address"],
            "register.read": services["register"],
            "register.write": services["register"],
            "register.list": services["register"],
            "memory.read": services["memory"],
            "memory.write": services["memory"],
            "memory.typed": services["memory"],
            "breakpoint.set": services["breakpoint"],
            "breakpoint.list": services["breakpoint"],
            "symbol.query": services["symbol"],
            "variable.read": services["variable"],
            "variable.write": services["variable"],
            "command.execute": services["command"],
            "function.evaluate": services["function"],
            "practice.run": hasattr(self.debugger, "cmm"),
            "practice.arguments": hasattr(self.debugger, "cmm"),
            "practice.macro": services["practice"],
            "direct_access": services["direct_access"],
        }
        return BackendCapabilities(
            backend="pyrcl",
            services=services,
            features=features,
            breakpoint=breakpoint,
        )

    def command(self, command: str) -> Any:
        return self._call("command.execute", self.debugger.cmd, command)

    def function(self, function: str) -> Any:
        return self._call("function.evaluate", self.debugger.fnc, function)

    def address_parse(self, text: str) -> Any:
        return self._call("address.parse", self.debugger.address.from_string, text)

    def address_create(self, *, access: str | None, value: int) -> Any:
        return self._call("address.create", self.debugger.address, access=access, value=value)

    def register_read(self, name: str, *, core: int | None = None) -> Any:
        if core is None:
            return self._call("register.read", self.debugger.register.read, name)
        return self._call("register.read", self.debugger.register.read, name, core=core)

    def register_write(self, name: str, value: int, *, core: int | None = None) -> Any:
        if core is None:
            return self._call("register.write", self.debugger.register.write, name, value)
        return self._call("register.write", self.debugger.register.write, name, value, core=core)

    def register_read_many(
        self,
        names: Sequence[str],
        *,
        core: int | None = None,
    ) -> list[Any]:
        return [self.register_read(name, core=core) for name in names]

    def register_list(self, *, core: int | None = None, unit: str | None = None) -> list[Any]:
        kwargs: dict[str, Any] = {}
        if core is not None:
            kwargs["core"] = core
        if unit is not None:
            kwargs["unit"] = unit
        return list(self._call("register.list", self.debugger.register.read_all, **kwargs))

    def memory_read(self, address: Any, *, length: int) -> bytes:
        return bytes(self._call("memory.read", self.debugger.memory.read, address, length=length))

    def memory_write(self, address: Any, data: bytes) -> Any:
        return self._call("memory.write", self.debugger.memory.write, address, data)

    def memory_read_typed(
        self,
        address: Any,
        *,
        type_name: str,
        byteorder: str | None = None,
    ) -> Any:
        suffix = _TYPE_METHODS[type_name]
        method = getattr(self.debugger.memory, f"read_{suffix}")
        kwargs = {}
        if byteorder is not None and _TYPE_WIDTH[type_name] > 1:
            kwargs["byteorder"] = byteorder
        return self._call("memory.read.typed", method, address, **kwargs)

    def memory_write_typed(
        self,
        address: Any,
        value: int | float,
        *,
        type_name: str,
        byteorder: str | None = None,
    ) -> Any:
        suffix = _TYPE_METHODS[type_name]
        method = getattr(self.debugger.memory, f"write_{suffix}")
        kwargs = {}
        if byteorder is not None and _TYPE_WIDTH[type_name] > 1:
            kwargs["byteorder"] = byteorder
        return self._call("memory.write.typed", method, address, value, **kwargs)

    def _breakpoint_enum(self, category: str, value: str | None) -> Any:
        if value is None:
            return None
        prototype = self._call("breakpoint.parameters", self.debugger.breakpoint)
        enum_class = {
            "type": prototype.Type,
            "implementation": prototype.Impl,
            "action": prototype.Action,
        }[category]
        name = value.upper()
        try:
            return enum_class[name]
        except KeyError as exc:
            raise Trace32BackendError(
                BackendErrorCode.BREAKPOINT_ERROR,
                f"unsupported breakpoint {category}: {value}",
                operation="breakpoint.set",
                details={"category": category, "value": value, "supported": _enum_names(enum_class)},
            ) from exc

    def breakpoint_set(
        self,
        *,
        address: Any,
        size: int | None = None,
        type_name: str | None = None,
        impl_name: str | None = None,
        action_name: str | None = None,
        core: int | None = None,
        enabled: bool = True,
    ) -> Any:
        kwargs: dict[str, Any] = {"address": address, "enabled": enabled}
        if size is not None:
            kwargs["size"] = size
        if type_name is not None:
            kwargs["type_"] = self._breakpoint_enum("type", type_name)
        if impl_name is not None:
            kwargs["impl"] = self._breakpoint_enum("implementation", impl_name)
        if action_name is not None:
            kwargs["action"] = self._breakpoint_enum("action", action_name)
        if core is not None:
            kwargs["core"] = core
        return self._call("breakpoint.set", self.debugger.breakpoint.set, **kwargs)

    def breakpoint_list(self) -> list[Any]:
        return list(self._call("breakpoint.list", self.debugger.breakpoint.list))

    def _breakpoint_at(self, index: int) -> Any:
        entries = self.breakpoint_list()
        if index < 0 or index >= len(entries):
            raise Trace32BackendError(
                BackendErrorCode.BREAKPOINT_NOT_FOUND,
                f"breakpoint index out of range: {index}",
                operation="breakpoint.lookup",
                details={"index": index, "count": len(entries)},
            )
        return entries[index]

    def breakpoint_delete(self, index: int) -> Any:
        return self._call("breakpoint.delete", self._breakpoint_at(index).delete)

    def breakpoint_enable(self, index: int) -> Any:
        return self._call("breakpoint.enable", self._breakpoint_at(index).enable)

    def breakpoint_disable(self, index: int) -> Any:
        return self._call("breakpoint.disable", self._breakpoint_at(index).disable)

    def breakpoint_clear(self) -> int:
        entries = self.breakpoint_list()
        for entry in entries:
            self._call("breakpoint.delete", entry.delete)
        return len(entries)

    def symbol_query_by_name(self, name: str) -> Any:
        return self._call("symbol.query.name", self.debugger.symbol.query_by_name, name)

    def symbol_query_by_address(self, address: Any) -> Any:
        return self._call("symbol.query.address", self.debugger.symbol.query_by_address, address)

    def variable_read(self, name: str) -> Any:
        return self._call("variable.read", self.debugger.variable.read, name)

    def variable_write(self, name: str, value: Any) -> Any:
        return self._call("variable.write", self.debugger.variable.write, name, value)

    def practice_run(
        self,
        command: str,
        *,
        arguments: Sequence[str] = (),
        timeout: float | None = None,
    ) -> Any:
        rendered = " ".join([_practice_token(command), *(_practice_token(item) for item in arguments)])
        if timeout is None:
            return self._call("practice.run", self.debugger.cmm, rendered)
        return self._call("practice.run", self.debugger.cmm, rendered, timeout=timeout)

    def macro_get(self, name: str) -> Any:
        return self._call("practice.macro.get", self.debugger.practice.get_macro, name)

    def macro_set(self, name: str, value: str) -> Any:
        return self._call("practice.macro.set", self.debugger.practice.set_macro, name, value)

    def direct_access(self) -> Any:
        if not hasattr(self.debugger, "directaccess"):
            raise Trace32BackendError(
                BackendErrorCode.UNSUPPORTED_OPERATION,
                "PYRCL direct access is unavailable",
                operation="direct_access",
            )
        return self.debugger.directaccess
