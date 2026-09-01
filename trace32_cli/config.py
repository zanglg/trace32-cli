"""TRACE32 CLI configuration resolution.

Persistent precedence, highest first:
  --config > project > user > defaults

Explicit CLI connection/profile options are applied above persistent config.
Environment variables are intentionally not part of runtime resolution.

Project configuration is discovered from the current working directory upward.
The nearest ancestor containing ``.trace32/config.toml`` is the project root.
This supports subprojects and monorepos without requiring configuration to live
at the Git repository top-level. Git top-level is only a fallback when no
project TRACE32 configuration is found in the ancestor chain.

When no profile and no host are configured, the CLI defaults to the local
PowerView endpoint at localhost:20001. A selected profile never falls back to
that implicit local endpoint: it must resolve a host explicitly from
configuration or CLI options.
"""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10
    import tomli as tomllib  # type: ignore

CONFIG_FIELDS = ("host", "port", "protocol", "timeout", "packlen")
DEFAULTS: dict[str, Any] = {
    "host": None,
    "port": 20001,
    "protocol": "TCP",
    "timeout": 10.0,
    "packlen": None,
}
IMPLICIT_LOCAL_HOST = "localhost"
IMPLICIT_LOCAL_SOURCE = "implicit-local-default"


class ConfigError(RuntimeError):
    pass


class ProfileHostMissing(ConfigError):
    def __init__(self, profile: str, profile_source: str | None):
        self.profile = profile
        self.profile_source = profile_source
        super().__init__(
            f"profile {profile!r} does not resolve a TRACE32 host; "
            "named profiles never fall back to the implicit localhost endpoint"
        )


def _nearest_project_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".trace32" / "config.toml").is_file():
            return candidate
    return None


def _git_root() -> Path | None:
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
    return None


def project_root() -> Path:
    return _nearest_project_root() or _git_root() or Path.cwd().resolve()


def user_config_path() -> Path:
    if os.name == "nt" and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / "trace32-cli" / "config.toml"
    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "trace32-cli" / "config.toml"


def config_locations() -> dict[str, str]:
    root = project_root()
    return {
        "user": str(user_config_path()),
        "project": str(root / ".trace32" / "config.toml"),
    }


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            value = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"unable to read config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"config root must be a TOML table: {path}")
    return value


def load_layered_config(explicit: str | None = None) -> list[tuple[str, Path, dict[str, Any]]]:
    root = project_root()
    candidates: list[tuple[str, Path]] = [
        ("user", user_config_path()),
        ("project", root / ".trace32" / "config.toml"),
    ]
    if explicit:
        candidates.append(("explicit", Path(explicit).expanduser().resolve()))

    layers = []
    for label, path in candidates:
        if path.is_file():
            layers.append((label, path, _read_toml(path)))
        elif label == "explicit":
            raise ConfigError(f"explicit config file does not exist: {path}")
    return layers


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def merged_config(explicit: str | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for _label, _path, data in load_layered_config(explicit):
        merged = _deep_merge(merged, data)
    return merged


def _coerce(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"port", "packlen"}:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field} must be an integer, got {value!r}") from exc
    if field == "timeout":
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"timeout must be numeric, got {value!r}") from exc
    return str(value)


def resolve_runtime(args) -> tuple[dict[str, Any], dict[str, Any]]:
    root = project_root()
    layers = load_layered_config(getattr(args, "config", None))

    profile = None
    profile_source = None
    for _label, path, data in layers:
        if data.get("default") is not None:
            profile = str(data["default"])
            profile_source = str(path)

    if getattr(args, "profile", None):
        profile = args.profile
        profile_source = "cli:--profile"

    runtime = copy.deepcopy(DEFAULTS)
    sources = {key: "built-in" for key in CONFIG_FIELDS if runtime.get(key) is not None}

    for _label, path, data in layers:
        connection = data.get("connection", {})
        if connection is not None and not isinstance(connection, dict):
            raise ConfigError(f"[connection] must be a table in {path}")
        for field in CONFIG_FIELDS:
            if isinstance(connection, dict) and field in connection:
                runtime[field] = _coerce(field, connection[field])
                sources[field] = str(path)

        if profile is not None:
            profiles = data.get("profiles", {})
            if profiles is not None and not isinstance(profiles, dict):
                raise ConfigError(f"[profiles] must be a table in {path}")
            entry = profiles.get(profile) if isinstance(profiles, dict) else None
            if entry is not None and not isinstance(entry, dict):
                raise ConfigError(f"[profiles.{profile}] must be a table in {path}")
            if isinstance(entry, dict):
                for field in CONFIG_FIELDS:
                    if field in entry:
                        runtime[field] = _coerce(field, entry[field])
                        sources[field] = str(path)

    cli_map = {
        "host": "--host",
        "port": "--port",
        "protocol": "--protocol",
        "timeout": "--timeout",
        "packlen": "--packlen",
    }
    for field, flag in cli_map.items():
        value = getattr(args, field, None)
        if value is not None:
            runtime[field] = _coerce(field, value)
            sources[field] = f"cli:{flag}"

    if runtime["host"] in (None, ""):
        if profile is not None:
            raise ProfileHostMissing(profile, profile_source)
        runtime["host"] = IMPLICIT_LOCAL_HOST
        sources["host"] = IMPLICIT_LOCAL_SOURCE

    runtime["profile"] = profile
    meta = {
        "project_root": str(root),
        "files": [{"layer": label, "path": str(path)} for label, path, _data in layers],
        "sources": {"profile": profile_source, **sources},
    }
    return runtime, meta
