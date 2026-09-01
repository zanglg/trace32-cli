"""CLI handlers that expose Layer 1 debugger semantics."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from trace32_cli import cli as core
from trace32_cli.layer0 import PyrclBackend

from .debugger import Debugger
from .models import AddressLocation, DebugContext, SourceLocation, SymbolLocation, WatchAccess


def _debugger(raw: Any) -> Debugger:
    return Debugger(PyrclBackend(raw))


def _context(args) -> DebugContext | None:
    core_index = getattr(args, "core", None)
    return DebugContext(core=core_index) if core_index is not None else None


def _location(args):
    kind = getattr(args, "kind", "address")
    text = args.location
    if kind == "address":
        return AddressLocation(text)
    if kind == "symbol":
        return SymbolLocation(text)
    line = getattr(args, "line", None)
    if line is None:
        raise core.CliError(
            "SOURCE_LINE_REQUIRED",
            "--line is required when --kind source is selected",
            core.EXIT_INVALID_INPUT,
        )
    return SourceLocation(text, line)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    breakpoint_fields = ("address", "size", "type", "type_", "impl", "action", "core", "enabled")
    if hasattr(value, "address") and hasattr(value, "enabled"):
        result = {}
        for field in breakpoint_fields:
            try:
                item = getattr(value, field)
            except Exception:
                continue
            if item is not None:
                result["type" if field == "type_" else field] = _plain(item)
        if result:
            return result
    if hasattr(value, "__dict__"):
        return {
            key: _plain(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _error(code: str, action: str, exc: Exception) -> core.CliError:
    exit_code = core.EXIT_INVALID_INPUT if isinstance(exc, (ValueError, IndexError)) else core.EXIT_OPERATION
    if isinstance(exc, TimeoutError):
        code = "TIMEOUT"
    return core.CliError(code, f"{action}: {exc}", exit_code)


def h_target_attach(dbg, _args):
    try:
        _debugger(dbg).target_attach()
        return {"attached": True}
    except Exception as exc:
        raise _error("TARGET_ATTACH_FAILED", "unable to attach target", exc) from exc


def h_target_detach(dbg, _args):
    try:
        _debugger(dbg).target_detach()
        return {"detached": True}
    except Exception as exc:
        raise _error("TARGET_DETACH_FAILED", "unable to detach target", exc) from exc


def h_target_up(dbg, _args):
    try:
        _debugger(dbg).target_up()
        return {"up": True}
    except Exception as exc:
        raise _error("TARGET_UP_FAILED", "unable to bring target up", exc) from exc


def h_target_reset(dbg, _args):
    try:
        _debugger(dbg).target_reset()
        return {"reset": True}
    except Exception as exc:
        raise _error("TARGET_RESET_FAILED", "unable to reset target", exc) from exc


def h_target_state(dbg, _args):
    try:
        return {"state": _debugger(dbg).state().value}
    except Exception as exc:
        raise _error("TARGET_STATE_FAILED", "unable to query target state", exc) from exc


def h_target_info(dbg, _args):
    try:
        return _plain(_debugger(dbg).target_info())
    except Exception as exc:
        raise _error("TARGET_INFO_FAILED", "unable to discover target", exc) from exc


def h_exec_run(dbg, _args):
    try:
        return {"state": _debugger(dbg).continue_execution().value}
    except Exception as exc:
        raise _error("EXEC_RUN_FAILED", "unable to continue execution", exc) from exc


def h_exec_halt(dbg, _args):
    try:
        return _plain(_debugger(dbg).halt())
    except Exception as exc:
        raise _error("EXEC_HALT_FAILED", "unable to halt execution", exc) from exc


def h_exec_step(dbg, _args):
    try:
        return _plain(_debugger(dbg).step())
    except Exception as exc:
        raise _error("EXEC_STEP_FAILED", "unable to step", exc) from exc


def h_exec_stepi(dbg, _args):
    try:
        return _plain(_debugger(dbg).step_instruction())
    except Exception as exc:
        raise _error("EXEC_STEPI_FAILED", "unable to instruction-step", exc) from exc


def h_exec_source_step(dbg, _args):
    try:
        return _plain(_debugger(dbg).step_source())
    except Exception as exc:
        raise _error("EXEC_SOURCE_STEP_FAILED", "unable to source-step", exc) from exc


def h_exec_next(dbg, _args):
    try:
        return _plain(_debugger(dbg).next())
    except Exception as exc:
        raise _error("EXEC_NEXT_FAILED", "unable to step over", exc) from exc


def h_exec_finish(dbg, _args):
    try:
        return _plain(_debugger(dbg).finish())
    except Exception as exc:
        raise _error("EXEC_FINISH_FAILED", "unable to finish current frame", exc) from exc


def h_exec_run_to(dbg, args):
    try:
        return {
            "state": _debugger(dbg).run_to(_location(args)).value,
            "kind": args.kind,
            "location": args.location,
        }
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("EXEC_RUN_TO_FAILED", "unable to run to location", exc) from exc


def h_exec_wait(dbg, args):
    try:
        return _plain(_debugger(dbg).wait(timeout=args.wait_timeout, poll_interval=args.poll_interval))
    except Exception as exc:
        raise _error("EXEC_WAIT_FAILED", "unable to wait for target stop", exc) from exc


def h_exec_stop_reason(dbg, _args):
    try:
        return _plain(_debugger(dbg).current_stop_event())
    except Exception as exc:
        raise _error("STOP_REASON_FAILED", "unable to inspect stop state", exc) from exc


def h_context_current(dbg, _args):
    try:
        return _plain(_debugger(dbg).context_current())
    except Exception as exc:
        raise _error("CONTEXT_FAILED", "unable to inspect current context", exc) from exc


def h_addr_parse(dbg, args):
    try:
        addr = _debugger(dbg).address_parse(args.address, access=args.access)
        return {
            "input": args.address,
            "access": getattr(addr, "access", None),
            "value": getattr(addr, "value", None),
            "repr": str(addr),
        }
    except Exception as exc:
        raise _error("INVALID_ADDRESS", "unable to parse address", exc) from exc


def h_reg_read(dbg, args):
    try:
        values = _debugger(dbg).register_read_many(args.names, context=_context(args))
        return [
            {
                "name": name,
                "value": getattr(reg, "value", reg),
                "fvalue": getattr(reg, "fvalue", None),
            }
            for name, reg in zip(args.names, values)
        ]
    except Exception as exc:
        raise _error("REGISTER_READ_FAILED", "unable to read register", exc) from exc


def h_reg_write(dbg, args):
    debugger = _debugger(dbg)
    written = []
    try:
        for item in args.assignments:
            if "=" not in item:
                raise ValueError(f"expected NAME=VALUE, got {item}")
            name, value = item.split("=", 1)
            number = core._int(value)
            debugger.register_write(name, number, context=_context(args))
            written.append({"name": name, "value": number})
        return written
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("REGISTER_WRITE_FAILED", "unable to write register", exc) from exc


def h_reg_list(dbg, args):
    try:
        registers = _debugger(dbg).register_list(context=_context(args), unit=args.unit)
        needle = args.contains.lower() if args.contains else None
        result = []
        for reg in registers:
            name = getattr(reg, "name", None)
            if name is None:
                name = str(reg)
            if needle and needle not in str(name).lower():
                continue
            result.append(
                {
                    "name": name,
                    "unit": getattr(reg, "unit", None),
                    "core": getattr(reg, "core", None),
                    "value": getattr(reg, "value", None),
                    "fvalue": getattr(reg, "fvalue", None),
                }
            )
        return result
    except Exception as exc:
        raise _error("REGISTER_LIST_FAILED", "unable to list registers", exc) from exc


def h_mem_read(dbg, args):
    try:
        addr, values = _debugger(dbg).memory_read_typed(
            args.address,
            type_name=args.type,
            count=args.count,
            byteorder=args.byteorder,
            access=args.access,
        )
        return {
            "address": str(addr),
            "type": args.type,
            "count": args.count,
            "value": values[0] if args.count == 1 else values,
        }
    except Exception as exc:
        raise _error("MEMORY_READ_FAILED", "unable to read memory", exc) from exc


def h_mem_write(dbg, args):
    try:
        values = [float(value) if args.type in {"f32", "f64"} else core._int(value) for value in args.values]
        addr, written = _debugger(dbg).memory_write_typed(
            args.address,
            values,
            type_name=args.type,
            byteorder=args.byteorder,
            access=args.access,
        )
        return {"address": str(addr), "type": args.type, "value": written}
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("MEMORY_WRITE_FAILED", "unable to write memory", exc) from exc


def h_mem_dump(dbg, args):
    try:
        addr, data = _debugger(dbg).memory_dump(args.address, length=args.length, access=args.access)
        return {"address": str(addr), "length": args.length, "hex": data.hex()}
    except Exception as exc:
        raise _error("MEMORY_DUMP_FAILED", "unable to dump memory", exc) from exc


def h_mem_write_bytes(dbg, args):
    try:
        data = bytes.fromhex(args.hexdata)
        addr = _debugger(dbg).memory_write_bytes(args.address, data, access=args.access)
        return {"address": str(addr), "length": len(data), "hex": data.hex()}
    except ValueError as exc:
        raise core.CliError("INVALID_HEX", f"invalid hex payload: {exc}", core.EXIT_INVALID_INPUT) from exc
    except Exception as exc:
        raise _error("MEMORY_WRITE_FAILED", "unable to write memory bytes", exc) from exc


def h_mem_search(dbg, args):
    try:
        pattern = bytes.fromhex(args.hexdata)
        hits = _debugger(dbg).memory_search(args.address, length=args.length, pattern=pattern, access=args.access)
        return {"address": args.address, "length": args.length, "pattern": pattern.hex(), "hits": hits}
    except Exception as exc:
        raise _error("MEMORY_SEARCH_FAILED", "unable to search memory", exc) from exc


def h_mem_compare(dbg, args):
    try:
        expected = bytes.fromhex(args.hexdata)
        result = _debugger(dbg).memory_compare(args.address, expected, access=args.access)
        result["expected"] = expected.hex()
        result["actual"] = result["actual"].hex()
        return result
    except Exception as exc:
        raise _error("MEMORY_COMPARE_FAILED", "unable to compare memory", exc) from exc


def h_mem_fill(dbg, args):
    try:
        pattern = bytes.fromhex(args.hexdata)
        addr = _debugger(dbg).memory_fill(args.address, length=args.length, pattern=pattern, access=args.access)
        return {"address": str(addr), "length": args.length, "pattern": pattern.hex()}
    except Exception as exc:
        raise _error("MEMORY_FILL_FAILED", "unable to fill memory", exc) from exc


def h_sym_name(dbg, args):
    try:
        return _plain(_debugger(dbg).symbol_by_name(args.name))
    except Exception as exc:
        raise _error("SYMBOL_NOT_FOUND", "unable to resolve symbol", exc) from exc


def h_sym_addr(dbg, args):
    try:
        return _plain(_debugger(dbg).symbol_by_address(args.address, access=args.access))
    except Exception as exc:
        raise _error("SYMBOL_NOT_FOUND", "unable to resolve address symbol", exc) from exc


def h_var_read(dbg, args):
    try:
        value = _debugger(dbg).variable_read(args.name)
        return {"name": args.name, "value": getattr(value, "value", value)}
    except Exception as exc:
        raise _error("VARIABLE_READ_FAILED", "unable to read variable", exc) from exc


def h_var_write(dbg, args):
    try:
        value = _debugger(dbg).variable_write(args.name, args.value)
        return {"name": args.name, "value": getattr(value, "value", args.value)}
    except Exception as exc:
        raise _error("VARIABLE_WRITE_FAILED", "unable to write variable", exc) from exc


def h_expr_eval(dbg, args):
    try:
        return {"expression": args.expression, "value": _debugger(dbg).expression_evaluate(args.expression)}
    except Exception as exc:
        raise _error("EXPRESSION_EVALUATION_FAILED", "unable to evaluate expression", exc) from exc


def h_expr_assign(dbg, args):
    try:
        _debugger(dbg).expression_assign(args.expression, args.value)
        return {"expression": args.expression, "value": args.value}
    except Exception as exc:
        raise _error("EXPRESSION_ASSIGN_FAILED", "unable to assign expression", exc) from exc


def h_type_describe(dbg, args):
    try:
        return {"expression": args.expression, "type": _debugger(dbg).type_describe(args.expression)}
    except Exception as exc:
        raise _error("TYPE_DESCRIBE_FAILED", "unable to describe type", exc) from exc


def h_bp_set(dbg, args):
    try:
        return _plain(_debugger(dbg).breakpoint_set(AddressLocation(args.address), core=args.core))
    except Exception as exc:
        raise _error("BREAKPOINT_SET_FAILED", "unable to set breakpoint", exc) from exc


def h_bp_add(dbg, args):
    try:
        return _plain(
            _debugger(dbg).breakpoint_set(
                _location(args),
                core=args.core,
                size=args.size,
                implementation=args.implementation,
                action=args.bp_action,
            )
        )
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("BREAKPOINT_SET_FAILED", "unable to set breakpoint", exc) from exc


def h_bp_list(dbg, _args):
    try:
        return [_plain(item) for item in _debugger(dbg).breakpoint_list()]
    except Exception as exc:
        raise _error("BREAKPOINT_LIST_FAILED", "unable to list breakpoints", exc) from exc


def h_bp_delete(dbg, args):
    try:
        _debugger(dbg).breakpoint_delete(args.index)
        return {"index": args.index, "deleted": True}
    except Exception as exc:
        raise _error("BREAKPOINT_NOT_FOUND", "unable to delete breakpoint", exc) from exc


def h_bp_enable(dbg, args):
    try:
        _debugger(dbg).breakpoint_enable(args.index)
        return {"index": args.index, "enabled": True}
    except Exception as exc:
        raise _error("BREAKPOINT_NOT_FOUND", "unable to enable breakpoint", exc) from exc


def h_bp_disable(dbg, args):
    try:
        _debugger(dbg).breakpoint_disable(args.index)
        return {"index": args.index, "enabled": False}
    except Exception as exc:
        raise _error("BREAKPOINT_NOT_FOUND", "unable to disable breakpoint", exc) from exc


def h_bp_clear(dbg, _args):
    try:
        return {"deleted": _debugger(dbg).breakpoint_clear()}
    except Exception as exc:
        raise _error("BREAKPOINT_CLEAR_FAILED", "unable to clear breakpoints", exc) from exc


def h_watch_add(dbg, args):
    try:
        return _plain(
            _debugger(dbg).watchpoint_set(
                _location(args),
                access=WatchAccess(args.watch_access),
                core=args.core,
                size=args.size,
                implementation=args.implementation,
            )
        )
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("WATCHPOINT_SET_FAILED", "unable to set watchpoint", exc) from exc


def h_watch_list(dbg, _args):
    try:
        items = []
        for index, item in enumerate(_debugger(dbg).breakpoint_list()):
            type_value = getattr(item, "type_", None)
            name = getattr(type_value, "name", str(type_value) if type_value is not None else "")
            if name in {"READ", "WRITE", "RW"}:
                rendered = _plain(item)
                if isinstance(rendered, dict):
                    rendered = {"index": index, **rendered}
                items.append(rendered)
        return items
    except Exception as exc:
        raise _error("WATCHPOINT_LIST_FAILED", "unable to list watchpoints", exc) from exc


def h_watch_delete(dbg, args):
    return h_bp_delete(dbg, args)


def h_source_current(dbg, _args):
    try:
        return _plain(_debugger(dbg).source_current())
    except Exception as exc:
        raise _error("SOURCE_CURRENT_FAILED", "unable to resolve current source", exc) from exc


def h_source_resolve(dbg, args):
    try:
        return _plain(_debugger(dbg).source_resolve(_location(args)))
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("SOURCE_RESOLVE_FAILED", "unable to resolve source location", exc) from exc


def h_source_list(dbg, args):
    try:
        return _debugger(dbg).source_list(limit=args.limit)
    except Exception as exc:
        raise _error("SOURCE_LIST_FAILED", "unable to list source files", exc) from exc


def h_insn_current(dbg, _args):
    try:
        return _plain(_debugger(dbg).instruction_disassemble())
    except Exception as exc:
        raise _error("DISASSEMBLE_FAILED", "unable to disassemble current instruction", exc) from exc


def h_insn_disasm(dbg, args):
    try:
        return _plain(_debugger(dbg).instruction_disassemble(_location(args)))
    except core.CliError:
        raise
    except Exception as exc:
        raise _error("DISASSEMBLE_FAILED", "unable to disassemble instruction", exc) from exc


def h_stack_backtrace(dbg, args):
    try:
        return _plain(_debugger(dbg).stack_backtrace(max_frames=args.max_frames))
    except Exception as exc:
        raise _error("STACK_BACKTRACE_FAILED", "unable to build backtrace", exc) from exc


def h_frame_up(dbg, _args):
    try:
        return _plain(_debugger(dbg).frame_up())
    except Exception as exc:
        raise _error("FRAME_UP_FAILED", "unable to select caller frame", exc) from exc


def h_frame_down(dbg, _args):
    try:
        return _plain(_debugger(dbg).frame_down())
    except Exception as exc:
        raise _error("FRAME_DOWN_FAILED", "unable to select callee frame", exc) from exc


def h_program_list(dbg, args):
    try:
        return _debugger(dbg).program_list(limit=args.limit)
    except Exception as exc:
        raise _error("PROGRAM_LIST_FAILED", "unable to list loaded programs", exc) from exc


def h_program_load_elf(dbg, args):
    try:
        _debugger(dbg).program_load_elf(args.file, symbols_only=False)
        return {"file": args.file, "format": "elf", "symbols_only": False}
    except Exception as exc:
        raise _error("PROGRAM_LOAD_FAILED", "unable to load ELF", exc) from exc


def h_program_load_symbols(dbg, args):
    try:
        _debugger(dbg).program_load_elf(args.file, symbols_only=True)
        return {"file": args.file, "format": "elf", "symbols_only": True}
    except Exception as exc:
        raise _error("SYMBOL_LOAD_FAILED", "unable to load ELF symbols", exc) from exc


def h_program_load_binary(dbg, args):
    try:
        _debugger(dbg).program_load_binary(args.file, args.address)
        return {"file": args.file, "format": "binary", "address": args.address}
    except Exception as exc:
        raise _error("PROGRAM_LOAD_FAILED", "unable to load binary", exc) from exc
