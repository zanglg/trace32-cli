"""Protocols for the TRACE32 capability layer."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .capabilities import BackendCapabilities


class Trace32Backend(Protocol):
    """Layer 0 contract consumed by the generic debugger layer.

    Layer 0 exposes TRACE32/PYRCL capabilities without adding architecture
    semantics. Register names, address classes, breakpoint enums, and direct
    access objects remain backend-visible values.
    """

    def capabilities(self) -> BackendCapabilities:
        """Describe capabilities of the connected backend/runtime."""

    def breakpoint_parameters(self) -> dict[str, list[str]]:
        """Return supported breakpoint type/implementation/action enum names."""

    def command(self, command: str) -> Any:
        """Execute a TRACE32 debugger command."""

    def function(self, function: str) -> Any:
        """Evaluate a TRACE32 debugger function."""

    def address_parse(self, text: str) -> Any:
        """Parse a TRACE32 address expression."""

    def address_create(self, *, access: str | None, value: int) -> Any:
        """Create a TRACE32 address object from access class and byte offset."""

    def register_read(self, name: str, *, core: int | None = None) -> Any:
        """Read one register by its backend-visible name."""

    def register_write(self, name: str, value: int, *, core: int | None = None) -> Any:
        """Write one register by its backend-visible name."""

    def register_read_many(
        self,
        names: Sequence[str],
        *,
        core: int | None = None,
    ) -> list[Any]:
        """Read multiple registers without interpreting architecture semantics."""

    def register_list(self, *, core: int | None = None, unit: str | None = None) -> list[Any]:
        """Return registers exposed by the current target/debug context."""

    def memory_read(self, address: Any, *, length: int) -> bytes:
        """Read raw bytes from a TRACE32 address object."""

    def memory_write(self, address: Any, data: bytes) -> Any:
        """Write raw bytes to a TRACE32 address object."""

    def memory_read_typed(
        self,
        address: Any,
        *,
        type_name: str,
        byteorder: str | None = None,
    ) -> Any:
        """Read one typed scalar using the PYRCL memory service."""

    def memory_write_typed(
        self,
        address: Any,
        value: int | float,
        *,
        type_name: str,
        byteorder: str | None = None,
    ) -> Any:
        """Write one typed scalar using the PYRCL memory service."""

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
        """Create a breakpoint using normalized backend enum names."""

    def breakpoint_list(self) -> list[Any]:
        """Return all current breakpoint objects."""

    def breakpoint_delete(self, index: int) -> Any:
        """Delete one breakpoint by list index."""

    def breakpoint_enable(self, index: int) -> Any:
        """Enable one breakpoint by list index."""

    def breakpoint_disable(self, index: int) -> Any:
        """Disable one breakpoint by list index."""

    def breakpoint_clear(self) -> int:
        """Delete all current breakpoints and return the number removed."""

    def symbol_query_by_name(self, name: str) -> Any:
        """Resolve a symbol by name."""

    def symbol_query_by_address(self, address: Any) -> Any:
        """Resolve a symbol by address."""

    def variable_read(self, name: str) -> Any:
        """Read a debugger variable by name."""

    def variable_write(self, name: str, value: Any) -> Any:
        """Write a debugger variable by name."""

    def practice_run(
        self,
        command: str,
        *,
        arguments: Sequence[str] = (),
        timeout: float | None = None,
    ) -> Any:
        """Execute a PRACTICE/CMM script command with positional arguments."""

    def macro_get(self, name: str) -> Any:
        """Read one PRACTICE macro."""

    def macro_set(self, name: str, value: str) -> Any:
        """Write one PRACTICE macro."""

    def direct_access(self) -> Any:
        """Return PYRCL direct-access service for expert Layer 0 consumers."""
