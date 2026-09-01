"""Stable Layer 0 error taxonomy for TRACE32 backends."""

from __future__ import annotations

from enum import Enum
from typing import Any


class BackendErrorCode(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    TIMEOUT = "TIMEOUT"
    INVALID_ADDRESS = "INVALID_ADDRESS"
    REGISTER_NOT_FOUND = "REGISTER_NOT_FOUND"
    REGISTER_ERROR = "REGISTER_ERROR"
    MEMORY_ACCESS_ERROR = "MEMORY_ACCESS_ERROR"
    BREAKPOINT_NOT_FOUND = "BREAKPOINT_NOT_FOUND"
    BREAKPOINT_ERROR = "BREAKPOINT_ERROR"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    VARIABLE_ERROR = "VARIABLE_ERROR"
    PRACTICE_ERROR = "PRACTICE_ERROR"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    TRACE32_COMMAND_ERROR = "TRACE32_COMMAND_ERROR"
    TRACE32_FUNCTION_ERROR = "TRACE32_FUNCTION_ERROR"
    BACKEND_ERROR = "BACKEND_ERROR"


class Trace32BackendError(RuntimeError):
    """Backend-neutral error raised by Layer 0 adapters."""

    def __init__(
        self,
        code: BackendErrorCode,
        message: str,
        *,
        operation: str,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.operation = operation
        self.recoverable = recoverable
        self.details = details or {}


def normalize_backend_error(operation: str, exc: Exception) -> Trace32BackendError:
    """Translate PYRCL/backend exceptions into stable Layer 0 categories.

    PYRCL's public exception hierarchy is useful but backend-specific. Matching
    by class name keeps this module independent of PYRCL internals and allows
    future backends to reuse the same stable error envelope.
    """

    if isinstance(exc, Trace32BackendError):
        return exc

    name = type(exc).__name__
    details = {"exception_type": name}
    lower_operation = operation.lower()

    if isinstance(exc, TimeoutError) or "Timeout" in name:
        return Trace32BackendError(
            BackendErrorCode.TIMEOUT,
            str(exc) or "TRACE32 operation timed out",
            operation=operation,
            recoverable=True,
            details=details,
        )

    if isinstance(exc, ConnectionError) or name.startswith("ApiConnection"):
        return Trace32BackendError(
            BackendErrorCode.NOT_CONNECTED,
            str(exc) or "TRACE32 backend connection is unavailable",
            operation=operation,
            recoverable=True,
            details=details,
        )

    if name.startswith("Address"):
        code = BackendErrorCode.INVALID_ADDRESS
    elif name == "RegisterNotFoundError":
        code = BackendErrorCode.REGISTER_NOT_FOUND
    elif name.startswith("Register"):
        code = BackendErrorCode.REGISTER_ERROR
    elif name.startswith("Memory"):
        code = BackendErrorCode.MEMORY_ACCESS_ERROR
    elif name == "BreakpointNotFoundError" or isinstance(exc, IndexError):
        code = BackendErrorCode.BREAKPOINT_NOT_FOUND
    elif name.startswith("Breakpoint"):
        code = BackendErrorCode.BREAKPOINT_ERROR
    elif name.startswith("Symbol"):
        code = BackendErrorCode.SYMBOL_NOT_FOUND
    elif name.startswith("Variable"):
        code = BackendErrorCode.VARIABLE_ERROR
    elif name.startswith("Practice"):
        code = BackendErrorCode.PRACTICE_ERROR
    elif isinstance(exc, (AttributeError, NotImplementedError)):
        code = BackendErrorCode.UNSUPPORTED_OPERATION
    elif lower_operation.startswith("command"):
        code = BackendErrorCode.TRACE32_COMMAND_ERROR
    elif lower_operation.startswith("function"):
        code = BackendErrorCode.TRACE32_FUNCTION_ERROR
    else:
        code = BackendErrorCode.BACKEND_ERROR

    return Trace32BackendError(
        code,
        str(exc) or f"TRACE32 backend operation failed: {operation}",
        operation=operation,
        recoverable=False,
        details=details,
    )
