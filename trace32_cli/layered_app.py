"""Public layered CLI assembly.

This module keeps the established CLI/configuration shell from :mod:`trace32_cli.app`
while routing debugger operations through Layer 1 -> Layer 0 -> PYRCL.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from . import app as legacy_app
from . import cli as core
from .config import CONFIG_FIELDS, ConfigError, ProfileHostMissing, resolve_runtime
from .layer1 import handlers as layered

QUICK_START = legacy_app.QUICK_START

_LAYERED_MUTATING = {
    "target detach",
    "target up",
    "target reset",
    "exec continue",
    "exec stepi",
    "exec source-step",
    "exec next",
    "exec finish",
    "exec run-to",
    "mem fill",
    "expr assign",
    "bp add",
    "bp clear",
    "watch add",
    "watch delete",
    "program load-elf",
    "program load-symbols",
    "program load-binary",
}


def _actions(parser: argparse.ArgumentParser, resource: str) -> argparse._SubParsersAction:
    return legacy_app._top_subparsers(legacy_app._child_parser(parser, resource))


def _override(parser: argparse.ArgumentParser, path: tuple[str, ...], handler, command: str) -> None:
    child = legacy_app._child_parser(parser, *path)
    local = bool(child.get_default("local"))
    core._handler(child, handler, command, local=local)


def _location_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("location", help="address, symbol, or source file depending on --kind")
    parser.add_argument(
        "--kind",
        choices=("address", "symbol", "source"),
        default="address",
        help="location interpretation; architecture-specific register names remain opaque elsewhere",
    )
    parser.add_argument("--line", type=int, help="source line; required with --kind source")


def _install_overrides(parser: argparse.ArgumentParser) -> None:
    # Existing public commands retain their grammar but now enter Layer 1.
    for path, handler in (
        (("target", "attach"), layered.h_target_attach),
        (("target", "state"), layered.h_target_state),
        (("target", "info"), layered.h_target_info),
        (("exec", "halt"), layered.h_exec_halt),
        (("exec", "run"), layered.h_exec_run),
        (("exec", "step"), layered.h_exec_step),
        (("addr", "parse"), layered.h_addr_parse),
        (("reg", "read"), layered.h_reg_read),
        (("reg", "write"), layered.h_reg_write),
        (("reg", "list"), layered.h_reg_list),
        (("mem", "read"), layered.h_mem_read),
        (("mem", "write"), layered.h_mem_write),
        (("mem", "dump"), layered.h_mem_dump),
        (("mem", "write-bytes"), layered.h_mem_write_bytes),
        (("sym", "name"), layered.h_sym_name),
        (("sym", "addr"), layered.h_sym_addr),
        (("var", "read"), layered.h_var_read),
        (("var", "write"), layered.h_var_write),
        (("bp", "set"), layered.h_bp_set),
        (("bp", "list"), layered.h_bp_list),
        (("bp", "delete"), layered.h_bp_delete),
        (("bp", "enable"), layered.h_bp_enable),
        (("bp", "disable"), layered.h_bp_disable),
    ):
        _override(parser, path, handler, " ".join(path))


def _install_target(parser: argparse.ArgumentParser) -> None:
    actions = _actions(parser, "target")
    for name, handler, help_text in (
        ("detach", layered.h_target_detach, "detach/down the current TRACE32 target"),
        ("up", layered.h_target_up, "bring the configured target up"),
        ("reset", layered.h_target_reset, "reset the target using SYStem.RESetTarget"),
    ):
        p = actions.add_parser(name, help=help_text)
        core._handler(p, handler, f"target {name}")


def _install_execution(parser: argparse.ArgumentParser) -> None:
    actions = _actions(parser, "exec")
    for name, handler, help_text in (
        ("continue", layered.h_exec_run, "continue target execution; alias of exec run"),
        ("state", layered.h_target_state, "query normalized execution state"),
        ("stepi", layered.h_exec_stepi, "single instruction step using TRACE32 Step.Asm"),
        ("source-step", layered.h_exec_source_step, "source-level step using TRACE32 Step.Hll"),
        ("next", layered.h_exec_next, "step over the current source operation"),
        ("finish", layered.h_exec_finish, "run/step until the current frame returns"),
        ("stop-reason", layered.h_exec_stop_reason, "inspect the current stop event and program pointer"),
    ):
        p = actions.add_parser(name, help=help_text)
        core._handler(p, handler, f"exec {name}")

    p = actions.add_parser("run-to", help="continue until an address, symbol, or source location")
    _location_arguments(p)
    core._handler(p, layered.h_exec_run_to, "exec run-to")

    p = actions.add_parser("wait", help="wait for the target to stop")
    p.add_argument("--timeout", dest="wait_timeout", type=float, default=None)
    p.add_argument("--poll-interval", type=float, default=0.05)
    core._handler(p, layered.h_exec_wait, "exec wait")


def _install_context(parser: argparse.ArgumentParser) -> None:
    top = legacy_app._top_subparsers(parser)
    context = top.add_parser("context", help="inspect the current debugger execution context")
    actions = context.add_subparsers(dest="action", required=True)
    p = actions.add_parser("current", help="show selected core/frame/source context")
    core._handler(p, layered.h_context_current, "context current")


def _install_memory(parser: argparse.ArgumentParser) -> None:
    actions = _actions(parser, "mem")
    p = actions.add_parser("search", help="search a memory range for a hexadecimal byte pattern")
    p.add_argument("address")
    p.add_argument("length", type=int)
    p.add_argument("hexdata")
    p.add_argument("--access")
    core._handler(p, layered.h_mem_search, "mem search")

    p = actions.add_parser("compare", help="compare memory bytes with a hexadecimal payload")
    p.add_argument("address")
    p.add_argument("hexdata")
    p.add_argument("--access")
    core._handler(p, layered.h_mem_compare, "mem compare")

    p = actions.add_parser("fill", help="fill a memory range with a repeated hexadecimal pattern")
    p.add_argument("address")
    p.add_argument("length", type=int)
    p.add_argument("hexdata")
    p.add_argument("--access")
    core._handler(p, layered.h_mem_fill, "mem fill")


def _install_breakpoints(parser: argparse.ArgumentParser) -> None:
    actions = _actions(parser, "bp")
    p = actions.add_parser("add", help="set a breakpoint at an address, symbol, or source location")
    _location_arguments(p)
    p.add_argument("--core", type=int)
    p.add_argument("--size", type=int)
    p.add_argument("--implementation", choices=("auto", "soft", "onchip", "hard", "mark"))
    p.add_argument("--action", dest="bp_action")
    core._handler(p, layered.h_bp_add, "bp add")

    p = actions.add_parser("clear", help="delete all current breakpoints/watchpoints")
    core._handler(p, layered.h_bp_clear, "bp clear")

    top = legacy_app._top_subparsers(parser)
    watch = top.add_parser("watch", help="data read/write/access watchpoints")
    watch_actions = watch.add_subparsers(dest="action", required=True)
    p = watch_actions.add_parser("add", help="add a data watchpoint")
    _location_arguments(p)
    p.add_argument("--access", dest="watch_access", choices=("read", "write", "access"), default="write")
    p.add_argument("--core", type=int)
    p.add_argument("--size", type=int)
    p.add_argument("--implementation", choices=("auto", "soft", "onchip", "hard", "mark"))
    core._handler(p, layered.h_watch_add, "watch add")
    p = watch_actions.add_parser("list", help="list data watchpoints")
    core._handler(p, layered.h_watch_list, "watch list")
    p = watch_actions.add_parser("delete", help="delete a watchpoint by breakpoint-list index")
    p.add_argument("index", type=int)
    core._handler(p, layered.h_watch_delete, "watch delete")


def _install_expressions(parser: argparse.ArgumentParser) -> None:
    top = legacy_app._top_subparsers(parser)
    expr = top.add_parser("expr", help="evaluate or assign source-language expressions")
    actions = expr.add_subparsers(dest="action", required=True)
    p = actions.add_parser("eval", help="evaluate an expression using TRACE32 Var.VALUE")
    p.add_argument("expression")
    core._handler(p, layered.h_expr_eval, "expr eval")
    p = actions.add_parser("assign", help="assign an expression using TRACE32 Var.Assign")
    p.add_argument("expression")
    p.add_argument("value")
    core._handler(p, layered.h_expr_assign, "expr assign")

    type_resource = top.add_parser("type", help="source-language type inspection")
    actions = type_resource.add_subparsers(dest="action", required=True)
    p = actions.add_parser("describe", help="describe the type of an expression")
    p.add_argument("expression")
    core._handler(p, layered.h_type_describe, "type describe")


def _install_source_instruction(parser: argparse.ArgumentParser) -> None:
    top = legacy_app._top_subparsers(parser)
    source = top.add_parser("source", help="source-level location and file operations")
    actions = source.add_subparsers(dest="action", required=True)
    p = actions.add_parser("current", help="show source location for the program pointer")
    core._handler(p, layered.h_source_current, "source current")
    p = actions.add_parser("resolve", help="resolve an address, symbol, or source location")
    _location_arguments(p)
    core._handler(p, layered.h_source_resolve, "source resolve")
    p = actions.add_parser("list", help="list source files known to TRACE32")
    p.add_argument("--limit", type=int, default=1024)
    core._handler(p, layered.h_source_list, "source list")

    insn = top.add_parser("insn", help="instruction/disassembly operations")
    actions = insn.add_subparsers(dest="action", required=True)
    p = actions.add_parser("current", help="disassemble the instruction at the program pointer")
    core._handler(p, layered.h_insn_current, "insn current")
    p = actions.add_parser("disasm", help="disassemble at an address, symbol, or source location")
    _location_arguments(p)
    core._handler(p, layered.h_insn_disasm, "insn disasm")


def _install_stack_frame(parser: argparse.ArgumentParser) -> None:
    top = legacy_app._top_subparsers(parser)
    stack = top.add_parser("stack", help="call stack inspection")
    actions = stack.add_subparsers(dest="action", required=True)
    p = actions.add_parser("backtrace", help="walk caller frames and restore the original selection")
    p.add_argument("--max-frames", type=int, default=64)
    core._handler(p, layered.h_stack_backtrace, "stack backtrace")

    frame = top.add_parser("frame", help="selected frame navigation")
    actions = frame.add_subparsers(dest="action", required=True)
    p = actions.add_parser("up", help="select caller frame")
    core._handler(p, layered.h_frame_up, "frame up")
    p = actions.add_parser("down", help="select callee frame")
    core._handler(p, layered.h_frame_down, "frame down")


def _install_program(parser: argparse.ArgumentParser) -> None:
    top = legacy_app._top_subparsers(parser)
    program = top.add_parser("program", help="loaded program, symbol, and image operations")
    actions = program.add_subparsers(dest="action", required=True)
    p = actions.add_parser("list", help="list programs known to TRACE32")
    p.add_argument("--limit", type=int, default=256)
    core._handler(p, layered.h_program_list, "program list")
    p = actions.add_parser("load-elf", help="load an ELF image and symbols")
    p.add_argument("file")
    core._handler(p, layered.h_program_load_elf, "program load-elf")
    p = actions.add_parser("load-symbols", help="load ELF symbols without target code")
    p.add_argument("file")
    core._handler(p, layered.h_program_load_symbols, "program load-symbols")
    p = actions.add_parser("load-binary", help="load a raw binary image at an explicit address")
    p.add_argument("file")
    p.add_argument("address")
    core._handler(p, layered.h_program_load_binary, "program load-binary")


def h_capabilities(dbg, args):
    data = legacy_app.h_capabilities(dbg, args)
    data["purpose"] = (
        "Layered, architecture-neutral debugger semantics over TRACE32/PYRCL, "
        "with explicit TRACE32 escape hatches."
    )
    data["debugger_model"] = {
        "layer2": "Agent Skill/workflows; strategy and debugging discipline",
        "layer1": "GDB-inspired generic debugger semantics; public structured CLI",
        "layer0": "PyRCL-inspired TRACE32 capability adapter",
        "architecture_registers": (
            "architecture-specific names are opaque strings in V1; no built-in register database"
        ),
        "location": ["address", "symbol", "source"],
        "context": ["target", "core", "process/inferior", "thread/task", "frame"],
    }
    data["safety"]["preferred_order"] = [
        "layer1 structured debugger operations",
        "layer0 typed/structured services",
        "raw fnc",
        "raw cmd",
        "practice/CMM for TRACE32-specific workflows",
    ]
    data["runtime_discovery"].update(
        {
            "execution": "t32 --json exec state",
            "stop_event": "t32 --json exec stop-reason",
            "context": "t32 --json context current",
            "source": "t32 --json source current",
        }
    )
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = legacy_app.build_parser()
    legacy_app.TARGET_MUTATING.update(_LAYERED_MUTATING)
    _install_overrides(parser)
    _install_target(parser)
    _install_execution(parser)
    _install_context(parser)
    _install_memory(parser)
    _install_breakpoints(parser)
    _install_expressions(parser)
    _install_source_instruction(parser)
    _install_stack_frame(parser)
    _install_program(parser)
    _override(parser, ("capabilities",), h_capabilities, "capabilities")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    if not raw:
        print(QUICK_START.rstrip())
        return core.EXIT_OK

    parser = build_parser()
    args = parser.parse_args(raw)
    args._root_parser = parser

    try:
        runtime_config, meta = resolve_runtime(args)
        for field in CONFIG_FIELDS:
            setattr(args, field, runtime_config[field])
        args.profile = runtime_config["profile"]
        args._config_meta = meta

        dbg = None
        try:
            if not args.local:
                dbg = legacy_app._connect_with_guidance(args)
            data = args.handler(dbg, args)
            if args.command_name == "test" and not args.json:
                print(legacy_app.selftest.format_human_report(data))
                return core.EXIT_OK
            return core._emit_success(args, args.command_name, data)
        finally:
            if dbg is not None:
                core._disconnect(dbg)
    except ProfileHostMissing as exc:
        return legacy_app._emit_app_error(
            args,
            core.CliError(
                "PROFILE_HOST_MISSING",
                str(exc),
                core.EXIT_CONNECTION,
                details=legacy_app._profile_host_missing_details(exc),
            ),
        )
    except ConfigError as exc:
        return legacy_app._emit_app_error(
            args,
            core.CliError("CONFIG_ERROR", str(exc), core.EXIT_INVALID_INPUT),
        )
    except core.CliError as exc:
        return legacy_app._emit_app_error(args, exc)
    except KeyboardInterrupt:
        return core.EXIT_INTERRUPTED
    except Exception as exc:
        return legacy_app._emit_app_error(
            args,
            core.CliError("PYRCL_OPERATION_FAILED", str(exc), core.EXIT_OPERATION),
        )


if __name__ == "__main__":
    raise SystemExit(main())
