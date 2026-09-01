"""Final public CLI assembly for the completed Layer 0/1 core."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from types import SimpleNamespace

from . import __version__
from . import app as legacy_app
from . import cli as core
from . import layered_app as base
from .config import CONFIG_FIELDS, ConfigError, ProfileHostMissing, resolve_runtime
from .layer1 import complete_handlers as completed


def _override(parser, path, handler, command):
    base._override(parser, path, handler, command)


def _install_completed_overrides(parser) -> None:
    for path, handler in (
        (("bp", "enums"), completed.h_bp_parameters),
        (("expr", "eval"), completed.h_expr_eval),
        (("type", "describe"), completed.h_type_describe),
        (("macro", "get"), completed.h_macro_get),
        (("macro", "set"), completed.h_macro_set),
        (("practice", "run"), completed.h_practice_run),
        (("raw", "cmd"), completed.h_raw_cmd),
        (("raw", "fnc"), completed.h_raw_fnc),
    ):
        _override(parser, path, handler, " ".join(path))

    practice = legacy_app._child_parser(parser, "practice", "run")
    practice.add_argument(
        "--timeout",
        dest="practice_timeout",
        type=float,
        default=None,
        help="PRACTICE completion timeout; 0 starts without polling, default waits indefinitely",
    )


def _install_backend(parser) -> None:
    top = legacy_app._top_subparsers(parser)
    backend = top.add_parser("backend", help="inspect the connected Layer 0 backend")
    actions = backend.add_subparsers(dest="action", required=True)
    p = actions.add_parser("capabilities", help="show connected backend services and feature support")
    core._handler(p, completed.h_backend_capabilities, "backend capabilities")


def _install_completed_context(parser) -> None:
    context_actions = legacy_app._top_subparsers(legacy_app._child_parser(parser, "context"))
    p = context_actions.add_parser("task-current", help="show current OS-awareness task when available")
    core._handler(p, completed.h_task_current, "context task-current")
    p = context_actions.add_parser("task-list", help="enumerate OS-awareness tasks")
    p.add_argument("--limit", type=int, default=1024)
    core._handler(p, completed.h_task_list, "context task-list")
    p = context_actions.add_parser("task-select", help="temporarily view a task context using Frame.TASK")
    p.add_argument("task", help="task magic/id or task name")
    core._handler(p, completed.h_task_select, "context task-select")

    frame_actions = legacy_app._top_subparsers(legacy_app._child_parser(parser, "frame"))
    p = frame_actions.add_parser("current", help="show selected frame and its zero-based stack level")
    p.add_argument("--max-depth", type=int, default=64)
    core._handler(p, completed.h_frame_current, "frame current")
    p = frame_actions.add_parser("select", help="select a zero-based frame level from the innermost frame")
    p.add_argument("level", type=int)
    p.add_argument("--max-depth", type=int, default=64)
    core._handler(p, completed.h_frame_select, "frame select")


def h_capabilities(dbg, args):
    data = base.h_capabilities(dbg, args)
    data["configuration"]["precedence"] = [
        "explicit CLI options",
        "--config file",
        "project config",
        "user config",
        "built-in defaults",
        "implicit localhost only when no profile/host is selected",
    ]
    data["debugger_model"].update(
        {
            "core_completion": {
                "layer0": [
                    "runtime capability negotiation",
                    "stable backend error taxonomy",
                    "normalized breakpoint parameters",
                    "PRACTICE arguments/timeouts",
                    "direct-access discovery",
                ],
                "layer1": [
                    "conservative stop-reason classification",
                    "task/frame context navigation",
                    "structured location resolution",
                    "structured expression/type results",
                    "structured disassembly results",
                ],
            },
            "stop_reason_policy": (
                "known for operations initiated by the CLI; inferred only for exact program-breakpoint PC "
                "matches; otherwise unknown rather than guessed"
            ),
        }
    )
    data["runtime_discovery"].update(
        {
            "backend": "t32 --json backend capabilities",
            "tasks": "t32 --json context task-list",
            "frame": "t32 --json frame current",
        }
    )
    data["errors"] = {
        "stable_layer0_codes": [
            "NOT_CONNECTED",
            "TIMEOUT",
            "INVALID_ADDRESS",
            "REGISTER_NOT_FOUND",
            "REGISTER_ERROR",
            "MEMORY_ACCESS_ERROR",
            "BREAKPOINT_NOT_FOUND",
            "BREAKPOINT_ERROR",
            "SYMBOL_NOT_FOUND",
            "VARIABLE_ERROR",
            "PRACTICE_ERROR",
            "UNSUPPORTED_OPERATION",
            "TRACE32_COMMAND_ERROR",
            "TRACE32_FUNCTION_ERROR",
            "BACKEND_ERROR",
        ]
    }
    return data


def build_parser():
    parser = base.build_parser()
    parser.epilog = """Agent discovery:
  t32 --json capabilities
  t32 --json schema

Setup verification:
  t32 skill install
  t32 --json profile current
  t32 --json doctor

Persistent configuration:
  user:    ~/.config/trace32-cli/config.toml
  project: <project>/.trace32/config.toml

Project config is discovered from the current directory upward.
Local PowerView defaults to localhost:20001 when no profile/host is configured.
Remote PowerView must be selected explicitly with --host or a profile.
"""
    _install_completed_overrides(parser)
    _install_backend(parser)
    _install_completed_context(parser)
    _override(parser, ("capabilities",), h_capabilities, "capabilities")
    return parser


def _bare_args():
    return SimpleNamespace(
        config=None,
        profile=None,
        host=None,
        port=None,
        protocol=None,
        timeout=None,
        packlen=None,
    )


def _format_quick_start() -> str:
    lines = [
        f"TRACE32 CLI {__version__}",
        "",
        "Structured TRACE32 debugging primitives over PYRCL.",
        "",
        "Resolved configuration:",
    ]
    try:
        runtime, meta = resolve_runtime(_bare_args())
        profile = runtime["profile"] or "(none)"
        endpoint = f"{runtime['host']}:{runtime['port']}/{runtime['protocol']}"
        lines.extend(
            [
                f"  project root: {meta['project_root']}",
                f"  profile:      {profile}",
                f"  endpoint:     {endpoint}",
            ]
        )
        files = meta["files"]
        if files:
            lines.append("  config files:")
            lines.extend(f"    {item['layer']}: {item['path']}" for item in files)
        else:
            lines.append("  config files: none (using built-in defaults)")
    except ConfigError as exc:
        lines.extend(["  configuration error:", f"    {exc}"])

    lines.extend(
        [
            "",
            "Agent discovery:",
            "  t32 --json capabilities",
            "  t32 --json schema",
            "",
            "Setup / verification:",
            "  t32 skill install",
            "  t32 --json profile current",
            "  t32 --json doctor",
            "",
            "Persistent configuration:",
            "  user:    ~/.config/trace32-cli/config.toml",
            "  project: <project>/.trace32/config.toml",
            "",
            "Project config is discovered from the current directory upward.",
            "Use --host/--port/--profile or --config for one-command overrides.",
            "",
            "Human help:",
            "  t32 --help",
        ]
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    if not raw:
        print(_format_quick_start())
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
            core.CliError("BACKEND_ERROR", str(exc), core.EXIT_OPERATION),
        )
