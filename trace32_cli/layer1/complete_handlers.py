"""Completed CLI handlers for the layered debugger API.

Existing handlers are reused for compatibility, but their Debugger and error
normalizer are replaced here so every structured operation uses the completed
Layer 1 facade and stable Layer 0 errors.
"""

from __future__ import annotations

from typing import Any

from trace32_cli import cli as cli_core
from trace32_cli.layer0 import BackendErrorCode, PyrclBackend, Trace32BackendError

from . import handlers as _base
from .core import Debugger

# Existing handler functions resolve these names from their defining module at
# call time, so updating them here upgrades the full compatibility surface.
_base.Debugger = Debugger
_legacy_error = _base._error


def _error(code: str, action: str, exc: Exception) -> cli_core.CliError:
    if isinstance(exc, Trace32BackendError):
        if exc.code is BackendErrorCode.NOT_CONNECTED:
            exit_code = cli_core.EXIT_CONNECTION
        elif exc.code in {BackendErrorCode.INVALID_ADDRESS, BackendErrorCode.BREAKPOINT_NOT_FOUND}:
            exit_code = cli_core.EXIT_INVALID_INPUT
        else:
            exit_code = cli_core.EXIT_OPERATION
        return cli_core.CliError(
            exc.code.value,
            f"{action}: {exc.message}",
            exit_code,
            details={
                "operation": exc.operation,
                "recoverable": exc.recoverable,
                **exc.details,
            },
        )
    return _legacy_error(code, action, exc)


# Install stable Layer 0 error mapping into reused handlers.
_base._error = _error


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


def _debugger(raw: Any) -> Debugger:
    return Debugger(PyrclBackend(raw))


def h_backend_capabilities(dbg, _args):
    try:
        return _base._plain(PyrclBackend(dbg).capabilities())
    except Exception as exc:
        raise _error("BACKEND_ERROR", "unable to discover backend capabilities", exc) from exc


def h_bp_parameters(dbg, _args):
    try:
        return PyrclBackend(dbg).breakpoint_parameters()
    except Exception as exc:
        raise _error("BREAKPOINT_ERROR", "unable to discover breakpoint parameters", exc) from exc


def h_expr_eval(dbg, args):
    try:
        return _base._plain(_debugger(dbg).expression_evaluate(args.expression))
    except Exception as exc:
        raise _error("EXPRESSION_EVALUATION_FAILED", "unable to evaluate expression", exc) from exc


def h_type_describe(dbg, args):
    try:
        return _base._plain(_debugger(dbg).type_describe(args.expression))
    except Exception as exc:
        raise _error("TYPE_DESCRIBE_FAILED", "unable to describe type", exc) from exc


def h_frame_current(dbg, args):
    try:
        return _base._plain(_debugger(dbg).frame_current(max_depth=args.max_depth))
    except Exception as exc:
        raise _error("FRAME_CURRENT_FAILED", "unable to inspect selected frame", exc) from exc


def h_frame_select(dbg, args):
    try:
        return _base._plain(
            _debugger(dbg).frame_select(args.level, max_depth=args.max_depth)
        )
    except Exception as exc:
        raise _error("FRAME_SELECT_FAILED", "unable to select frame", exc) from exc


def h_task_current(dbg, _args):
    try:
        task = _debugger(dbg).task_current()
        return {"available": task is not None, "task": _base._plain(task) if task else None}
    except Exception as exc:
        raise _error("CONTEXT_TASK_FAILED", "unable to inspect current task", exc) from exc


def h_task_list(dbg, args):
    try:
        return [_base._plain(task) for task in _debugger(dbg).task_list(limit=args.limit)]
    except Exception as exc:
        raise _error("CONTEXT_TASK_FAILED", "unable to list tasks", exc) from exc


def h_task_select(dbg, args):
    try:
        return _base._plain(_debugger(dbg).task_select(args.task))
    except Exception as exc:
        raise _error("CONTEXT_TASK_FAILED", "unable to select task context", exc) from exc


def h_macro_get(dbg, args):
    try:
        macro = PyrclBackend(dbg).macro_get(args.name)
        return {"name": args.name, "value": getattr(macro, "value", macro)}
    except Exception as exc:
        raise _error("PRACTICE_ERROR", "unable to read PRACTICE macro", exc) from exc


def h_macro_set(dbg, args):
    try:
        macro = PyrclBackend(dbg).macro_set(args.name, args.value)
        return {"name": args.name, "value": getattr(macro, "value", args.value)}
    except Exception as exc:
        raise _error("PRACTICE_ERROR", "unable to write PRACTICE macro", exc) from exc


def h_practice_run(dbg, args):
    try:
        PyrclBackend(dbg).practice_run(
            args.file,
            arguments=args.arguments,
            timeout=getattr(args, "practice_timeout", None),
        )
        return {
            "file": args.file,
            "arguments": list(args.arguments),
            "completed": getattr(args, "practice_timeout", None) != 0,
        }
    except Exception as exc:
        raise _error("PRACTICE_ERROR", "unable to execute PRACTICE script", exc) from exc


def h_raw_cmd(dbg, args):
    try:
        return PyrclBackend(dbg).command(args.command)
    except Exception as exc:
        raise _error("TRACE32_COMMAND_ERROR", "TRACE32 command failed", exc) from exc


def h_raw_fnc(dbg, args):
    try:
        return PyrclBackend(dbg).function(args.function)
    except Exception as exc:
        raise _error("TRACE32_FUNCTION_ERROR", "TRACE32 function failed", exc) from exc
