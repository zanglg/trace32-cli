"""Public CLI assembly, configuration, diagnostics, and discovery."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from importlib import metadata
from typing import Any

from . import __version__, runtime, selftest
from . import cli as core
from .config import (
    CONFIG_FIELDS,
    IMPLICIT_LOCAL_SOURCE,
    ConfigError,
    ProfileHostMissing,
    config_locations,
    merged_config,
    resolve_runtime,
)

TARGET_MUTATING = {
    "target attach",
    "exec halt",
    "exec run",
    "exec step",
    "reg write",
    "mem write",
    "mem write-bytes",
    "var write",
    "bp set",
    "bp delete",
    "bp enable",
    "bp disable",
    "macro set",
    "practice run",
    "raw cmd",
}

QUICK_START = f"""TRACE32 CLI {__version__}

Structured TRACE32 debugging primitives over PYRCL.

Agent discovery:
  t32 --json capabilities
  t32 --json schema

Setup after installation:
  t32 skill install
  t32 --json profile current
  t32 --json doctor

Local PowerView:
  no host configuration required; defaults to localhost:20001

Human help:
  t32 --help

Connection configuration:
  user:    ~/.config/trace32-cli/config.toml
  project: <repo>/.trace32/config.toml
  local:   <repo>/.trace32/config.local.toml

One-off overrides:
  --profile --host --port --protocol --timeout --packlen
"""


def _top_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise RuntimeError("subparser action not found")


def _child_parser(parser: argparse.ArgumentParser, *path: str) -> argparse.ArgumentParser:
    current = parser
    for name in path:
        current = _top_subparsers(current).choices[name]
    return current


def _argument_schema(action: argparse.Action) -> dict[str, Any]:
    if action.dest == "help":
        return {}
    item: dict[str, Any] = {
        "dest": action.dest,
        "required": bool(getattr(action, "required", False)),
    }
    if action.option_strings:
        item["flags"] = list(action.option_strings)
    else:
        item["positional"] = True
    if action.nargs is not None:
        item["nargs"] = action.nargs
    if action.choices is not None:
        item["choices"] = list(action.choices)
    if action.type is not None:
        item["type"] = getattr(action.type, "__name__", str(action.type))
    if action.default not in (None, argparse.SUPPRESS, False):
        item["default"] = action.default
    help_text = getattr(action, "help", None)
    if help_text and help_text is not argparse.SUPPRESS:
        item["help"] = help_text
    return item


def _command_schema(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    subparsers = None
    arguments = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers = action
        elif action.dest != "help":
            spec = _argument_schema(action)
            if spec:
                arguments.append(spec)

    if prefix:
        command = " ".join(prefix)
        item = {
            "usage": parser.format_usage().strip().removeprefix("usage: "),
            "description": parser.description,
            "arguments": arguments,
            "target_mutating": command in TARGET_MUTATING,
        }
        if command == "test":
            item["conditionally_mutating"] = True
            item["safety_source"] = "t32 --json capabilities -> self_test.safety"
        result[command] = item

    if subparsers is not None:
        for name, child in subparsers.choices.items():
            result.update(_command_schema(child, prefix + (name,)))
    return result


def _schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    globals_schema = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) or action.dest == "help":
            continue
        spec = _argument_schema(action)
        if spec:
            globals_schema.append(spec)
    return {
        "name": "trace32-cli",
        "version": __version__,
        "grammar": "t32 [GLOBAL_OPTIONS] RESOURCE [ACTION] [ARGS...]",
        "global_options": globals_schema,
        "commands": _command_schema(parser),
    }


def _connection_guidance(args) -> dict[str, Any]:
    sources = getattr(args, "_config_meta", {}).get("sources", {})
    host_source = sources.get("host")
    return {
        "connection": {
            "profile": args.profile,
            "host": args.host,
            "port": args.port,
            "protocol": args.protocol,
            "host_source": host_source,
            "implicit_local": host_source == IMPLICIT_LOCAL_SOURCE,
        },
        "local": {
            "default": "localhost:20001",
            "description": (
                "With no selected profile and no configured host, t32 uses localhost. "
                "Only configure a local host when overriding that default."
            ),
            "examples": ["t32 --json doctor", "t32 --port 20002 --json doctor"],
        },
        "remote": {
            "description": (
                "Remote PowerView endpoints must be explicit so a remote intent never "
                "silently falls back to localhost."
            ),
            "examples": [
                "t32 --host 192.168.1.20 --port 20001 --json doctor",
                "define [profiles.NAME] host and port, then use --profile NAME",
            ],
        },
        "inspect": ["t32 --json profile current", "t32 --json doctor"],
    }


def _connection_failure(exc: core.CliError, args) -> core.CliError:
    details = _connection_guidance(args)
    if details["connection"]["host_source"] == IMPLICIT_LOCAL_SOURCE:
        note = (
            "No host/profile was configured, so the implicit local endpoint was selected. "
            "If you intended a remote PowerView, pass --host or select a profile with a host."
        )
    else:
        note = (
            "Check the resolved endpoint with 't32 --json profile current'. "
            "Local PowerView can use localhost without host configuration; remote PowerView "
            "must use --host or a profile host."
        )
    return core.CliError(
        "CONNECTION_FAILED",
        f"{exc.message}. {note}",
        core.EXIT_CONNECTION,
        details=details,
    )


def _connect_with_guidance(args):
    try:
        return core._connect(args)
    except core.CliError as exc:
        if exc.code == "CONNECTION_FAILED":
            raise _connection_failure(exc, args) from exc
        raise


def _profile_host_missing_details(exc: ProfileHostMissing) -> dict[str, Any]:
    return {
        "profile": exc.profile,
        "profile_source": exc.profile_source,
        "local": {
            "description": "For zero-config local use, omit --profile and t32 defaults to localhost:20001.",
            "example": "t32 --json doctor",
        },
        "remote": {
            "description": "A named profile must resolve an explicit host.",
            "example_toml": (
                f"[profiles.{exc.profile}]\n"
                'host = "192.168.1.20"\n'
                "port = 20001"
            ),
            "example": f"t32 --profile {exc.profile} --json doctor",
        },
    }


def _emit_app_error(args, exc: core.CliError) -> int:
    if getattr(args, "command_name", None) == "test" and not args.json and isinstance(exc.details, dict):
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        print(selftest.format_human_report(exc.details), file=sys.stderr)
        return exc.exit_code
    result = core._emit_error(args, exc)
    if not args.json and exc.details is not None:
        print(
            json.dumps(exc.details, ensure_ascii=False, indent=2, default=core._json_default),
            file=sys.stderr,
        )
    return result


def h_capabilities(_dbg, args):
    schema = _schema(args._root_parser)
    resources: dict[str, list[str]] = {}
    for command in schema["commands"]:
        parts = command.split()
        resource = parts[0]
        action = " ".join(parts[1:]) if len(parts) > 1 else ""
        resources.setdefault(resource, [])
        if action:
            resources[resource].append(action)
    return {
        "name": "trace32-cli",
        "version": __version__,
        "purpose": "Structured, architecture-neutral TRACE32 debugging primitives over PYRCL.",
        "configuration": {
            "files": config_locations(),
            "precedence": [
                "explicit CLI options",
                "--config file",
                "project local config",
                "project config",
                "user config",
                "built-in defaults",
                "implicit localhost only when no profile/host is selected",
            ],
            "local_default": {
                "host": "localhost",
                "port": 20001,
                "guard": "selected profiles never fall back to implicit localhost",
            },
        },
        "resources": resources,
        "runtime_discovery": {
            "target": "t32 --json target info",
            "registers": "t32 --json reg list --core 0",
            "breakpoint_parameters": "t32 --json bp enums",
        },
        "self_test": selftest.capability_metadata(),
        "safety": {
            "preserve_crash_state_before_mutation": True,
            "target_mutating_commands": sorted(TARGET_MUTATING),
            "preferred_order": ["typed primitives", "raw fnc", "raw cmd"],
        },
        "next": {
            "exact_syntax": "t32 --json schema",
            "connection_diagnostics": "t32 --json doctor",
            "runtime_target": "t32 --json target info",
            "live_regression": "t32 test",
            "full_regression": "t32 test --all",
            "agent_guidance": "t32 skill show",
            "human_help": "t32 --help",
        },
    }


def h_schema(_dbg, args):
    return _schema(args._root_parser)


def _pyrcl_version() -> str | None:
    for package in ("lauterbach-trace32-rcl", "lauterbach_trace32_rcl"):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return None


def h_doctor(_dbg, args):
    host_source = args._config_meta["sources"].get("host")
    result: dict[str, Any] = {
        "healthy": False,
        "read_only": True,
        "cli": {"ok": True, "version": __version__},
        "configuration": {
            "profile": args.profile,
            "host": args.host,
            "port": args.port,
            "protocol": args.protocol,
            "timeout": args.timeout,
            "implicit_local": host_source == IMPLICIT_LOCAL_SOURCE,
            "files": args._config_meta["files"],
            "sources": args._config_meta["sources"],
        },
        "pyrcl": {"installed": False, "version": _pyrcl_version()},
        "powerview": {"configured": True, "reachable": False},
        "note": (
            "doctor only opens/closes the Remote API connection; it does not attach, "
            "halt, run, reset, or write target state."
        ),
    }

    try:
        core._load_pyrcl()
        result["pyrcl"]["installed"] = True
    except core.CliError as exc:
        result["pyrcl"]["error"] = exc.message
        return result

    dbg = None
    try:
        dbg = _connect_with_guidance(args)
        result["powerview"]["reachable"] = True
        result["healthy"] = True
    except core.CliError as exc:
        result["powerview"]["error"] = exc.message
        result["powerview"]["details"] = exc.details
    finally:
        if dbg is not None:
            core._disconnect(dbg)
    return result


def h_profile_list(_dbg, args):
    config = merged_config(args.config)
    profiles = config.get("profiles", {})
    output = []
    for name in sorted(profiles):
        entry = profiles[name] if isinstance(profiles[name], dict) else {}
        output.append(
            {
                "name": name,
                "description": entry.get("description"),
                "host": entry.get("host"),
                "port": entry.get("port"),
                "protocol": entry.get("protocol"),
                "default": name == config.get("default"),
            }
        )
    return output


def h_profile_show(_dbg, args):
    config = merged_config(args.config)
    profiles = config.get("profiles", {})
    if args.name not in profiles:
        raise core.CliError(
            "PROFILE_NOT_FOUND",
            f"profile not found: {args.name}",
            core.EXIT_INVALID_INPUT,
        )
    return {"name": args.name, **profiles[args.name]}


def h_profile_current(_dbg, args):
    host_source = args._config_meta["sources"].get("host")
    return {
        "profile": args.profile,
        "host": args.host,
        "port": args.port,
        "protocol": args.protocol,
        "timeout": args.timeout,
        "packlen": args.packlen,
        "configured": host_source != IMPLICIT_LOCAL_SOURCE,
        "implicit_local": host_source == IMPLICIT_LOCAL_SOURCE,
        "files": args._config_meta["files"],
        "sources": args._config_meta["sources"],
    }


def _install_runtime_commands(parser: argparse.ArgumentParser) -> None:
    target_actions = _top_subparsers(_child_parser(parser, "target"))
    p = target_actions.add_parser(
        "info",
        help="discover current CPU, architecture, core count, state, and endianness",
    )
    core._handler(p, runtime.h_target_info, "target info")

    bp_actions = _top_subparsers(_child_parser(parser, "bp"))
    p = bp_actions.add_parser(
        "enums",
        help="show breakpoint type/implementation/action enums from installed PYRCL",
    )
    core._handler(p, runtime.h_bp_enums, "bp enums")


def _enhance_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Structured TRACE32 debugging primitives over PYRCL. "
        "Agents should start with: t32 --json capabilities"
    )
    parser.epilog = """Agent discovery:
  t32 --json capabilities
  t32 --json schema

Setup verification:
  t32 skill install
  t32 --json profile current
  t32 --json doctor

Local PowerView defaults to localhost:20001 when no profile/host is configured.
Remote PowerView must be selected explicitly with --host or a profile.

Configuration:
  ~/.config/trace32-cli/config.toml
  <repo>/.trace32/config.toml
  <repo>/.trace32/config.local.toml
"""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter

    parser.set_defaults(host=None, port=None, protocol=None, timeout=None, packlen=None)
    parser.add_argument(
        "--profile",
        default=None,
        help="PowerView profile name; overrides the configured default",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="additional TOML config file, applied above project/user config",
    )

    _install_runtime_commands(parser)
    top = _top_subparsers(parser)

    p = top.add_parser(
        "capabilities",
        help="show machine-readable semantic capabilities; recommended Agent entry point",
    )
    core._handler(p, h_capabilities, "capabilities", True)

    p = top.add_parser(
        "schema",
        help="show exact machine-readable CLI command/argument schema",
    )
    core._handler(p, h_schema, "schema", True)

    p = top.add_parser(
        "doctor",
        help=(
            "diagnose CLI, PYRCL, configuration, and PowerView connectivity "
            "without changing target state"
        ),
    )
    core._handler(p, h_doctor, "doctor", True)

    p = top.add_parser(
        "test",
        help="run a selected live regression plan against the PowerView/target",
        description=(
            "Default is observation-only. --memory adds restored TRACE32 VM: scratch tests; "
            "--extended adds temporary breakpoint state; --execution adds Break/Step/Go; "
            "--all runs every registered self-test suite."
        ),
    )
    selftest.configure_parser(p)
    core._handler(p, selftest.h_test, "test")

    profile = top.add_parser("profile", help="inspect PowerView profiles from layered configuration")
    actions = profile.add_subparsers(dest="action", required=True)
    p = actions.add_parser("list", help="list configured profiles")
    core._handler(p, h_profile_list, "profile list", True)
    p = actions.add_parser("show", help="show one merged profile")
    p.add_argument("name")
    core._handler(p, h_profile_show, "profile show", True)
    p = actions.add_parser("current", help="show the effective current connection/profile")
    core._handler(p, h_profile_current, "profile current", True)

    return parser


def build_parser() -> argparse.ArgumentParser:
    return _enhance_parser(core.build_parser())


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
                dbg = _connect_with_guidance(args)
            data = args.handler(dbg, args)
            if args.command_name == "test" and not args.json:
                print(selftest.format_human_report(data))
                return core.EXIT_OK
            return core._emit_success(args, args.command_name, data)
        finally:
            if dbg is not None:
                core._disconnect(dbg)
    except ProfileHostMissing as exc:
        return _emit_app_error(
            args,
            core.CliError(
                "PROFILE_HOST_MISSING",
                str(exc),
                core.EXIT_CONNECTION,
                details=_profile_host_missing_details(exc),
            ),
        )
    except ConfigError as exc:
        return _emit_app_error(
            args,
            core.CliError("CONFIG_ERROR", str(exc), core.EXIT_INVALID_INPUT),
        )
    except core.CliError as exc:
        return _emit_app_error(args, exc)
    except KeyboardInterrupt:
        return core.EXIT_INTERRUPTED
    except Exception as exc:
        return _emit_app_error(
            args,
            core.CliError("PYRCL_OPERATION_FAILED", str(exc), core.EXIT_OPERATION),
        )


if __name__ == "__main__":
    raise SystemExit(main())
