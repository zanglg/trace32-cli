"""Low-level TRACE32 CLI primitives backed by documented PYRCL services.

This module owns the stable resource/action primitives. Architecture discovery,
configuration layering, and self-test policy live in separate modules.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from . import __version__

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PYRCL_MISSING = 10
EXIT_CONNECTION = 11
EXIT_OPERATION = 12
EXIT_INVALID_INPUT = 13
EXIT_INTERRUPTED = 130

SKILL_NAME = "t32"
SKILL_AGENTS = ("agents", "codex", "pi")
SKILL_SCOPES = ("user", "project")
MEMORY_TYPES = ("u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64")
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


class CliError(RuntimeError):
    def __init__(self, code: str, message: str, exit_code: int = EXIT_OPERATION, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details


def _json_default(value: Any):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        try:
            return value.value
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def _emit_success(args, command: str, data: Any) -> int:
    envelope = {"ok": True, "command": command, "data": data}
    if args.json:
        print(json.dumps(envelope, ensure_ascii=False, default=_json_default))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default))
    return EXIT_OK


def _emit_error(args, exc: CliError) -> int:
    envelope = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        envelope["error"]["details"] = exc.details
    if args.json:
        print(json.dumps(envelope, ensure_ascii=False, default=_json_default), file=sys.stderr)
    else:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
    return exc.exit_code


def _load_pyrcl():
    try:
        from lauterbach.trace32 import rcl as t32  # type: ignore
    except ImportError as exc:
        raise CliError(
            "PYRCL_NOT_INSTALLED",
            "PYRCL is not installed. Install trace32-cli with dependencies.",
            EXIT_PYRCL_MISSING,
        ) from exc
    return t32


def _connect(args):
    t32 = _load_pyrcl()
    kwargs = {
        "node": args.host,
        "port": args.port,
        "protocol": args.protocol,
        "timeout": args.timeout,
    }
    if args.packlen is not None:
        kwargs["packlen"] = args.packlen
    try:
        return t32.connect(**kwargs)
    except Exception as exc:
        raise CliError(
            "CONNECTION_FAILED",
            f"unable to connect to TRACE32 at {args.host}:{args.port}: {exc}",
            EXIT_CONNECTION,
        ) from exc


def _disconnect(dbg) -> None:
    try:
        dbg.disconnect()
    except Exception:
        pass


def _value(obj: Any) -> Any:
    return getattr(obj, "value", obj)


def _int(text: str) -> int:
    try:
        return int(text, 0)
    except ValueError as exc:
        raise CliError("INVALID_INTEGER", f"invalid integer: {text}", EXIT_INVALID_INPUT) from exc


def _address(dbg, text: str, access: str | None = None):
    value = text if ":" in text or not access else f"{access}:{text}"
    try:
        return dbg.address.from_string(value)
    except Exception as exc:
        raise CliError(
            "INVALID_ADDRESS",
            f"unable to parse TRACE32 address {value!r}: {exc}",
            EXIT_INVALID_INPUT,
        ) from exc


def _project_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except OSError:
        pass
    return Path.cwd().resolve()


def _skill_root(agent: str, scope: str) -> Path:
    if agent in {"agents", "codex"}:
        return (Path.home() if scope == "user" else _project_root()) / ".agents" / "skills"
    if agent == "pi":
        if scope == "user":
            return Path.home() / ".pi" / "agent" / "skills"
        return _project_root() / ".pi" / "skills"
    raise CliError("UNSUPPORTED_AGENT", f"unsupported agent: {agent}", EXIT_INVALID_INPUT)


def _skill_destination(args) -> Path:
    root = Path(args.dir).expanduser().resolve() if args.dir else _skill_root(args.agent, args.scope)
    return root / SKILL_NAME


def _bundled_skill():
    return resources.files("trace32_cli").joinpath("skills", SKILL_NAME)


def _copy_resource_tree(source, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, target)
        else:
            target.write_bytes(child.read_bytes())


def h_about(_dbg, _args):
    return {
        "name": "trace32-cli",
        "version": __version__,
        "cli": "t32",
        "pyrcl_dependency": "lauterbach-trace32-rcl>=1.1,<1.2",
    }


def h_skill_path(_dbg, args):
    path = _skill_destination(args)
    return {"skill": SKILL_NAME, "path": str(path), "installed": (path / "SKILL.md").is_file()}


def h_skill_status(_dbg, args):
    path = _skill_destination(args)
    installed = (path / "SKILL.md").is_file()
    metadata = None
    if installed and (path / ".t32-skill.json").is_file():
        try:
            metadata = json.loads((path / ".t32-skill.json").read_text(encoding="utf-8"))
        except Exception:
            metadata = None
    return {
        "skill": SKILL_NAME,
        "path": str(path),
        "installed": installed,
        "bundled_version": __version__,
        "installed_version": metadata.get("cli_version") if metadata else None,
    }


def h_skill_install(_dbg, args):
    destination = _skill_destination(args)
    marker = destination / "SKILL.md"
    if marker.exists() and not args.force:
        raise CliError(
            "SKILL_ALREADY_INSTALLED",
            f"skill already installed at {destination}; use --force to replace it",
            EXIT_INVALID_INPUT,
        )
    if destination.exists():
        shutil.rmtree(destination)
    _copy_resource_tree(_bundled_skill(), destination)
    (destination / ".t32-skill.json").write_text(
        json.dumps({"skill": SKILL_NAME, "cli_version": __version__}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"skill": SKILL_NAME, "path": str(destination), "installed": True}


def h_skill_uninstall(_dbg, args):
    destination = _skill_destination(args)
    if not destination.exists():
        return {"skill": SKILL_NAME, "path": str(destination), "removed": False}
    marker = destination / ".t32-skill.json"
    if not marker.exists() and not args.force:
        raise CliError(
            "SKILL_NOT_MANAGED",
            f"refusing to remove unrecognized skill directory {destination}; use --force",
            EXIT_INVALID_INPUT,
        )
    shutil.rmtree(destination)
    return {"skill": SKILL_NAME, "path": str(destination), "removed": True}


def h_skill_show(_dbg, _args):
    return _bundled_skill().joinpath("SKILL.md").read_text(encoding="utf-8")


def h_target_attach(dbg, _args):
    dbg.cmd("SYStem.Attach")
    return {"attached": True}


def h_target_state(dbg, _args):
    try:
        value = dbg.fnc("STATE.RUN()")
    except Exception:
        value = dbg.fnc("STATE()")
    return {"state": _value(value)}


def h_exec_halt(dbg, _args):
    dbg.cmd("Break")
    return {"state": "halted"}


def h_exec_run(dbg, _args):
    dbg.cmd("Go")
    return {"state": "running"}


def h_exec_step(dbg, _args):
    dbg.cmd("Step")
    return {"stepped": True}


def h_addr_parse(dbg, args):
    addr = _address(dbg, args.address, args.access)
    return {
        "input": args.address,
        "access": getattr(addr, "access", None),
        "value": getattr(addr, "value", None),
        "repr": str(addr),
    }


def h_reg_read(dbg, args):
    values = []
    for name in args.names:
        try:
            reg = dbg.register.read(name, core=args.core) if args.core is not None else dbg.register.read(name)
            values.append(
                {
                    "name": name,
                    "value": getattr(reg, "value", reg),
                    "fvalue": getattr(reg, "fvalue", None),
                }
            )
        except Exception as exc:
            raise CliError(
                "REGISTER_READ_FAILED",
                f"unable to read register {name}: {exc}",
                EXIT_OPERATION,
            ) from exc
    return values


def h_reg_write(dbg, args):
    written = []
    for item in args.assignments:
        if "=" not in item:
            raise CliError("INVALID_ASSIGNMENT", f"expected NAME=VALUE, got {item}", EXIT_INVALID_INPUT)
        name, value = item.split("=", 1)
        number = _int(value)
        if args.core is None:
            dbg.register.write(name, number)
        else:
            dbg.register.write(name, number, core=args.core)
        written.append({"name": name, "value": number})
    return written


def h_reg_list(dbg, args):
    kwargs = {}
    if args.core is not None:
        kwargs["core"] = args.core
    unit = getattr(args, "unit", None)
    if unit is not None:
        kwargs["unit"] = unit

    needle = args.contains.lower() if args.contains else None
    output = []
    for reg in dbg.register.read_all(**kwargs):
        # Avoid eager ``str(reg)``: PYRCL 1.1.x can overflow while formatting
        # unsigned high-bit register values even when ``reg.name`` is available.
        name = getattr(reg, "name", None)
        if name is None:
            name = str(reg)
        if needle and needle not in str(name).lower():
            continue
        output.append(
            {
                "name": name,
                "unit": getattr(reg, "unit", None),
                "core": getattr(reg, "core", None),
                "value": getattr(reg, "value", None),
                "fvalue": getattr(reg, "fvalue", None),
            }
        )
    return output


def _mem_method(prefix: str, type_name: str) -> str:
    mapping = {
        "u8": "uint8",
        "s8": "int8",
        "u16": "uint16",
        "s16": "int16",
        "u32": "uint32",
        "s32": "int32",
        "u64": "uint64",
        "s64": "int64",
        "f32": "single",
        "f64": "double",
    }
    return f"{prefix}_{mapping[type_name]}"


def _offset_address(dbg, address, offset: int):
    if offset == 0:
        return address
    value = getattr(address, "value", None)
    if value is None:
        raise CliError(
            "ADDRESS_OFFSET_UNSUPPORTED",
            "PYRCL address object does not expose a numeric value for multi-element access",
            EXIT_OPERATION,
        )
    return dbg.address(access=getattr(address, "access", None), value=value + offset)


def _typed_kwargs(type_name: str, byteorder: str | None) -> dict[str, Any]:
    if byteorder and _TYPE_WIDTH[type_name] > 1:
        return {"byteorder": byteorder}
    return {}


def h_mem_read(dbg, args):
    if args.count < 1:
        raise CliError("INVALID_COUNT", "--count must be >= 1", EXIT_INVALID_INPUT)

    addr = _address(dbg, args.address, args.access)
    method = getattr(dbg.memory, _mem_method("read", args.type))
    width = _TYPE_WIDTH[args.type]
    kwargs = _typed_kwargs(args.type, args.byteorder)
    values = [method(_offset_address(dbg, addr, index * width), **kwargs) for index in range(args.count)]
    value: Any = values[0] if args.count == 1 else values
    return {"address": str(addr), "type": args.type, "count": args.count, "value": value}


def h_mem_write(dbg, args):
    addr = _address(dbg, args.address, args.access)
    method = getattr(dbg.memory, _mem_method("write", args.type))
    width = _TYPE_WIDTH[args.type]
    kwargs = _typed_kwargs(args.type, args.byteorder)
    values = [float(value) if args.type in {"f32", "f64"} else _int(value) for value in args.values]
    for index, value in enumerate(values):
        method(_offset_address(dbg, addr, index * width), value, **kwargs)
    return {"address": str(addr), "type": args.type, "value": values}


def h_mem_dump(dbg, args):
    if args.length < 0:
        raise CliError("INVALID_LENGTH", "length must be >= 0", EXIT_INVALID_INPUT)
    addr = _address(dbg, args.address, args.access)
    data = dbg.memory.read(addr, length=args.length)
    return {"address": str(addr), "length": args.length, "hex": bytes(data).hex()}


def h_mem_write_bytes(dbg, args):
    addr = _address(dbg, args.address, args.access)
    try:
        data = bytes.fromhex(args.hexdata)
    except ValueError as exc:
        raise CliError("INVALID_HEX", f"invalid hex payload: {args.hexdata}", EXIT_INVALID_INPUT) from exc
    dbg.memory.write(addr, data)
    return {"address": str(addr), "length": len(data), "hex": data.hex()}


def h_sym_name(dbg, args):
    result = dbg.symbol.query_by_name(args.name)
    return vars(result) if hasattr(result, "__dict__") else result


def h_sym_addr(dbg, args):
    addr = _address(dbg, args.address, args.access)
    result = dbg.symbol.query_by_address(addr)
    return vars(result) if hasattr(result, "__dict__") else result


def h_var_read(dbg, args):
    value = dbg.variable.read(args.name)
    return {"name": args.name, "value": getattr(value, "value", value)}


def h_var_write(dbg, args):
    dbg.variable.write(args.name, args.value)
    return {"name": args.name, "value": args.value}


def h_bp_set(dbg, args):
    addr = _address(dbg, args.address, args.access)
    bp = dbg.breakpoint.set(address=addr, core=args.core)
    return vars(bp) if hasattr(bp, "__dict__") else bp


def h_bp_list(dbg, _args):
    return [vars(bp) if hasattr(bp, "__dict__") else str(bp) for bp in dbg.breakpoint.list()]


def _resolve_bp(dbg, index: int):
    entries = list(dbg.breakpoint.list())
    if index < 0 or index >= len(entries):
        raise CliError(
            "BREAKPOINT_NOT_FOUND",
            f"breakpoint index out of range: {index}",
            EXIT_INVALID_INPUT,
        )
    return entries[index]


def h_bp_delete(dbg, args):
    _resolve_bp(dbg, args.index).delete()
    return {"index": args.index, "deleted": True}


def h_bp_enable(dbg, args):
    _resolve_bp(dbg, args.index).enable()
    return {"index": args.index, "enabled": True}


def h_bp_disable(dbg, args):
    _resolve_bp(dbg, args.index).disable()
    return {"index": args.index, "enabled": False}


def h_macro_get(dbg, args):
    macro = dbg.practice.get_macro(args.name)
    return {"name": args.name, "value": getattr(macro, "value", macro)}


def h_macro_set(dbg, args):
    macro = dbg.practice.set_macro(args.name, args.value)
    return {"name": args.name, "value": getattr(macro, "value", args.value)}


def h_practice_run(dbg, args):
    if args.arguments:
        raise CliError(
            "PRACTICE_ARGUMENTS_UNSUPPORTED",
            "PYRCL cmm() accepts a command/file and timeout; positional script arguments are not supported by this CLI yet",
            EXIT_INVALID_INPUT,
        )
    return dbg.cmm(args.file)


def h_raw_cmd(dbg, args):
    return dbg.cmd(args.command)


def h_raw_fnc(dbg, args):
    return dbg.fnc(args.function)


def _add_skill_target_options(parser):
    parser.add_argument("--agent", choices=SKILL_AGENTS, default="agents")
    parser.add_argument("--scope", choices=SKILL_SCOPES, default="user")
    parser.add_argument("--dir", help="custom skills root; overrides --agent and --scope")


def _handler(parser, function, command: str, local: bool = False):
    parser.set_defaults(handler=function, command_name=command, local=local)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t32", description="Agent-friendly TRACE32 CLI via PYRCL")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--protocol")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--packlen", type=int)
    parser.add_argument("--json", action="store_true")

    resources_p = parser.add_subparsers(dest="resource", required=True)

    p = resources_p.add_parser("about", help="show CLI metadata")
    _handler(p, h_about, "about", True)

    skill = resources_p.add_parser("skill", help="manage the bundled Agent Skill")
    actions = skill.add_subparsers(dest="action", required=True)
    p = actions.add_parser("install")
    _add_skill_target_options(p)
    p.add_argument("--force", action="store_true")
    _handler(p, h_skill_install, "skill install", True)
    p = actions.add_parser("status")
    _add_skill_target_options(p)
    _handler(p, h_skill_status, "skill status", True)
    p = actions.add_parser("path")
    _add_skill_target_options(p)
    _handler(p, h_skill_path, "skill path", True)
    p = actions.add_parser("show")
    _handler(p, h_skill_show, "skill show", True)
    p = actions.add_parser("uninstall")
    _add_skill_target_options(p)
    p.add_argument("--force", action="store_true")
    _handler(p, h_skill_uninstall, "skill uninstall", True)

    target = resources_p.add_parser("target", help="target connection/state operations")
    actions = target.add_subparsers(dest="action", required=True)
    p = actions.add_parser("attach")
    _handler(p, h_target_attach, "target attach")
    p = actions.add_parser("state")
    _handler(p, h_target_state, "target state")

    execute = resources_p.add_parser("exec", help="execution control")
    actions = execute.add_subparsers(dest="action", required=True)
    for name, handler in (("halt", h_exec_halt), ("run", h_exec_run), ("step", h_exec_step)):
        p = actions.add_parser(name)
        _handler(p, handler, f"exec {name}")

    address = resources_p.add_parser("addr", help="TRACE32 address operations")
    actions = address.add_subparsers(dest="action", required=True)
    p = actions.add_parser("parse")
    p.add_argument("address")
    p.add_argument("--access")
    _handler(p, h_addr_parse, "addr parse")

    reg = resources_p.add_parser("reg", help="register operations")
    actions = reg.add_subparsers(dest="action", required=True)
    p = actions.add_parser("read")
    p.add_argument("names", nargs="+")
    p.add_argument("--core", type=int)
    _handler(p, h_reg_read, "reg read")
    p = actions.add_parser("write")
    p.add_argument("assignments", nargs="+")
    p.add_argument("--core", type=int)
    _handler(p, h_reg_write, "reg write")
    p = actions.add_parser("list")
    p.add_argument("--contains")
    p.add_argument("--core", type=int)
    p.add_argument("--unit", choices=("CPU", "FPU", "VPU"), default="CPU")
    _handler(p, h_reg_list, "reg list")

    mem = resources_p.add_parser("mem", help="memory operations")
    actions = mem.add_subparsers(dest="action", required=True)
    p = actions.add_parser("read")
    p.add_argument("address")
    p.add_argument("--access")
    p.add_argument("--type", choices=MEMORY_TYPES, default="u8")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--byteorder", choices=("little", "big"))
    _handler(p, h_mem_read, "mem read")
    p = actions.add_parser("write")
    p.add_argument("address")
    p.add_argument("values", nargs="+")
    p.add_argument("--access")
    p.add_argument("--type", choices=MEMORY_TYPES, default="u8")
    p.add_argument("--byteorder", choices=("little", "big"))
    _handler(p, h_mem_write, "mem write")
    p = actions.add_parser("dump")
    p.add_argument("address")
    p.add_argument("length", type=int)
    p.add_argument("--access")
    _handler(p, h_mem_dump, "mem dump")
    p = actions.add_parser("write-bytes")
    p.add_argument("address")
    p.add_argument("hexdata")
    p.add_argument("--access")
    _handler(p, h_mem_write_bytes, "mem write-bytes")

    sym = resources_p.add_parser("sym", help="symbol operations")
    actions = sym.add_subparsers(dest="action", required=True)
    p = actions.add_parser("name")
    p.add_argument("name")
    _handler(p, h_sym_name, "sym name")
    p = actions.add_parser("addr")
    p.add_argument("address")
    p.add_argument("--access")
    _handler(p, h_sym_addr, "sym addr")

    var = resources_p.add_parser("var", help="variable operations")
    actions = var.add_subparsers(dest="action", required=True)
    p = actions.add_parser("read")
    p.add_argument("name")
    _handler(p, h_var_read, "var read")
    p = actions.add_parser("write")
    p.add_argument("name")
    p.add_argument("value")
    _handler(p, h_var_write, "var write")

    bp = resources_p.add_parser("bp", help="breakpoint operations")
    actions = bp.add_subparsers(dest="action", required=True)
    p = actions.add_parser("set")
    p.add_argument("address")
    p.add_argument("--access")
    p.add_argument("--core", type=int)
    _handler(p, h_bp_set, "bp set")
    p = actions.add_parser("list")
    _handler(p, h_bp_list, "bp list")
    for name, handler in (("delete", h_bp_delete), ("enable", h_bp_enable), ("disable", h_bp_disable)):
        p = actions.add_parser(name)
        p.add_argument("index", type=int)
        _handler(p, handler, f"bp {name}")

    macro = resources_p.add_parser("macro", help="PRACTICE macro operations")
    actions = macro.add_subparsers(dest="action", required=True)
    p = actions.add_parser("get")
    p.add_argument("name")
    _handler(p, h_macro_get, "macro get")
    p = actions.add_parser("set")
    p.add_argument("name")
    p.add_argument("value")
    _handler(p, h_macro_set, "macro set")

    practice = resources_p.add_parser("practice", help="PRACTICE/CMM execution")
    actions = practice.add_subparsers(dest="action", required=True)
    p = actions.add_parser("run")
    p.add_argument("file")
    p.add_argument("arguments", nargs="*")
    _handler(p, h_practice_run, "practice run")

    raw = resources_p.add_parser("raw", help="generic TRACE32 command/function gateways")
    actions = raw.add_subparsers(dest="action", required=True)
    p = actions.add_parser("cmd")
    p.add_argument("command")
    _handler(p, h_raw_cmd, "raw cmd")
    p = actions.add_parser("fnc")
    p.add_argument("function")
    _handler(p, h_raw_fnc, "raw fnc")

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    dbg = None
    try:
        if not args.local:
            dbg = _connect(args)
        data = args.handler(dbg, args)
        return _emit_success(args, args.command_name, data)
    except CliError as exc:
        return _emit_error(args, exc)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except Exception as exc:
        return _emit_error(args, CliError("PYRCL_OPERATION_FAILED", str(exc), EXIT_OPERATION))
    finally:
        if dbg is not None:
            _disconnect(dbg)


if __name__ == "__main__":
    raise SystemExit(main())
