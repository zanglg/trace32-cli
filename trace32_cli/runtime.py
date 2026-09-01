"""Runtime TRACE32/PYRCL capability discovery.

Primitive register, memory, and breakpoint operations live in ``cli.py``. This
module only contains functionality whose purpose is runtime capability discovery.
"""

from __future__ import annotations

from typing import Any

from . import cli as core


def _optional_fnc(dbg, expression: str, unavailable: dict[str, str]) -> Any:
    try:
        return core._value(dbg.fnc(expression))
    except Exception as exc:
        unavailable[expression] = str(exc)
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    return None


def _architecture(cpu_family: Any, is_64bit: Any, arm64: Any) -> str | None:
    family = str(cpu_family).strip() if cpu_family not in (None, "") else ""
    upper = family.upper()
    is64 = _as_bool(is_64bit)
    arm64_value = _as_bool(arm64)

    if upper == "ARM" and arm64_value is True:
        return "AArch64"
    if upper == "ARM":
        return "ARM64" if is64 else "ARM"
    if "RISCV" in upper or "RISC-V" in upper:
        return "RISC-V64" if is64 else "RISC-V"
    return family or None


def h_target_info(dbg, _args):
    unavailable: dict[str, str] = {}
    cpu = _optional_fnc(dbg, "CPU()", unavailable)
    cpu_family = _optional_fnc(dbg, "CPUFAMILY()", unavailable)
    core_version = _optional_fnc(dbg, "CPUCOREVERSION()", unavailable)
    is_64bit = _optional_fnc(dbg, "CPUIS64BIT()", unavailable)
    configured_cores = _optional_fnc(dbg, "CONFIGNUMBER()", unavailable)
    big_endian = _optional_fnc(dbg, "SYStem.BIGENDIAN()", unavailable)
    running = _optional_fnc(dbg, "STATE.RUN()", unavailable)
    halted = _optional_fnc(dbg, "STATE.HALT()", unavailable)

    arm64 = None
    if str(cpu_family).strip().upper() == "ARM":
        arm64 = _optional_fnc(dbg, "ARM64()", unavailable)

    state = "unknown"
    if _as_bool(running) is True:
        state = "running"
    elif _as_bool(halted) is True:
        state = "halted"

    endian = None
    big_endian_bool = _as_bool(big_endian)
    if big_endian_bool is not None:
        endian = "big" if big_endian_bool else "little"

    result = {
        "cpu": cpu,
        "cpu_family": cpu_family,
        "core_version": core_version,
        "architecture": _architecture(cpu_family, is_64bit, arm64),
        "is_64bit": _as_bool(is_64bit),
        "configured_cores": configured_cores,
        "state": state,
        "endianness": endian,
    }
    if arm64 is not None:
        result["arm64"] = _as_bool(arm64)
    if unavailable:
        result["unavailable"] = unavailable
    return result


def _enum_members(enum_class) -> list[dict[str, Any]]:
    return [
        {"name": name, "value": member.value}
        for name, member in enum_class.__members__.items()
    ]


def h_bp_enums(dbg, _args):
    breakpoint = dbg.breakpoint()
    return {
        "type": _enum_members(breakpoint.Type),
        "impl": _enum_members(breakpoint.Impl),
        "action": _enum_members(breakpoint.Action),
    }
