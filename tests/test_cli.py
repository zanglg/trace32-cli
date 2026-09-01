import enum
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from trace32_cli import __version__, app, runtime, selftest
from trace32_cli import cli as core
from trace32_cli.config import ProfileHostMissing, resolve_runtime
from trace32_cli.entry import build_parser, main


def _isolated_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user-config"))


def test_version_and_parser_baseline():
    assert __version__ == "0.0.0"
    assert build_parser().prog == "t32"


def test_no_args_prints_setup_oriented_quick_start(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "t32 --json capabilities" in out
    assert "t32 skill install" in out
    assert "t32 --json doctor" in out
    assert "localhost:20001" in out


def test_local_discovery_commands(capsys):
    assert main(["--json", "about"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["version"] == "0.0.0"

    assert main(["--json", "capabilities"]) == 0
    capabilities = json.loads(capsys.readouterr().out)["data"]
    assert capabilities["configuration"]["local_default"]["host"] == "localhost"
    assert "environment_overrides" not in capabilities["configuration"]
    assert capabilities["self_test"]["plans"]["all"] == "t32 test --all"
    assert "skip-vm" not in json.dumps(capabilities)

    assert main(["--json", "schema"]) == 0
    schema = json.loads(capsys.readouterr().out)["data"]
    assert "target info" in schema["commands"]
    assert "bp enums" in schema["commands"]
    assert schema["commands"]["reg write"]["target_mutating"] is True
    assert schema["commands"]["test"]["conditionally_mutating"] is True
    test_flags = {
        flag
        for argument in schema["commands"]["test"]["arguments"]
        for flag in argument.get("flags", [])
    }
    assert {"--memory", "--extended", "--execution", "--all"} <= test_flags
    assert "--skip-vm" not in test_flags


def test_zero_config_defaults_to_localhost(tmp_path: Path, monkeypatch):
    _isolated_config(tmp_path, monkeypatch)
    args = build_parser().parse_args(["profile", "current"])
    runtime_config, meta = resolve_runtime(args)
    assert runtime_config["profile"] is None
    assert runtime_config["host"] == "localhost"
    assert runtime_config["port"] == 20001
    assert meta["sources"]["host"] == "implicit-local-default"


def test_selected_profile_never_falls_back_to_localhost(tmp_path: Path, monkeypatch):
    _isolated_config(tmp_path, monkeypatch)
    config_dir = tmp_path / ".trace32"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        'default = "remote"\n\n[profiles.remote]\nport = 20001\n',
        encoding="utf-8",
    )
    args = build_parser().parse_args(["profile", "current"])
    with pytest.raises(ProfileHostMissing):
        resolve_runtime(args)


def test_profile_host_missing_is_structured_error(tmp_path: Path, monkeypatch, capsys):
    _isolated_config(tmp_path, monkeypatch)
    config_dir = tmp_path / ".trace32"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        'default = "remote"\n\n[profiles.remote]\nport = 20001\n',
        encoding="utf-8",
    )
    assert main(["--json", "profile", "current"]) == core.EXIT_CONNECTION
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "PROFILE_HOST_MISSING"
    assert error["details"]["profile"] == "remote"


def test_connection_failure_explains_local_and_remote(tmp_path: Path, monkeypatch, capsys):
    _isolated_config(tmp_path, monkeypatch)

    def fail_connect(_args):
        raise core.CliError(
            "CONNECTION_FAILED",
            "unable to connect to TRACE32 at localhost:20001: refused",
            core.EXIT_CONNECTION,
        )

    monkeypatch.setattr(app.core, "_connect", fail_connect)
    assert main(["--json", "target", "info"]) == core.EXIT_CONNECTION
    details = json.loads(capsys.readouterr().err)["error"]["details"]
    assert details["connection"]["host_source"] == "implicit-local-default"
    assert details["local"]["default"] == "localhost:20001"
    assert "--host" in details["remote"]["examples"][0]


def _fake_report(failed=0):
    return {
        "plan": "read-only",
        "context": {
            "host": "localhost",
            "port": 20001,
            "host_source": "implicit-local-default",
            "profile": None,
            "core": 0,
            "pc": "0x1000",
            "target_address": "P:0x1000",
            "vm_scratch": None,
        },
        "safety": {},
        "summary": {"passed": 3 - failed, "failed": failed, "skipped": 0},
        "cases": [
            {"id": "reg.pc", "status": "fail", "error": {"message": "boom"}}
            if failed
            else {"id": "reg.pc", "status": "pass", "data": {"hex": "0x1000"}}
        ],
    }


def test_self_test_is_human_by_default_and_json_when_explicit(tmp_path: Path, monkeypatch, capsys):
    _isolated_config(tmp_path, monkeypatch)
    monkeypatch.setattr(app.core, "_connect", lambda _args: SimpleNamespace(disconnect=lambda: None))
    monkeypatch.setattr(selftest, "run_self_test", lambda _dbg, _args: _fake_report())

    assert main(["test"]) == 0
    human = capsys.readouterr().out
    assert human.startswith("TRACE32 CLI Self-Test")
    assert "PASS  reg.pc" in human

    assert main(["--json", "test"]) == 0
    machine = json.loads(capsys.readouterr().out)
    assert machine["command"] == "test"
    assert machine["data"]["summary"]["passed"] == 3


def test_self_test_failure_preserves_human_and_json_reports(tmp_path: Path, monkeypatch, capsys):
    _isolated_config(tmp_path, monkeypatch)
    monkeypatch.setattr(app.core, "_connect", lambda _args: SimpleNamespace(disconnect=lambda: None))
    monkeypatch.setattr(selftest, "run_self_test", lambda _dbg, _args: _fake_report(failed=1))

    assert main(["test"]) == core.EXIT_OPERATION
    assert "FAIL  reg.pc  boom" in capsys.readouterr().err

    assert main(["--json", "test"]) == core.EXIT_OPERATION
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "TEST_FAILED"
    assert error["details"]["summary"]["failed"] == 1


def test_self_test_vm_address_must_be_vm():
    class Address:
        access = "D"
        value = 0x1000

    dbg = SimpleNamespace(address=SimpleNamespace(from_string=lambda _text: Address()))
    args = SimpleNamespace(length=64, test_plan="memory", vm_address="D:0x1000")
    with pytest.raises(core.CliError) as caught:
        selftest.run_self_test(dbg, args)
    assert caught.value.code == "INVALID_TEST_VM_ADDRESS"


def test_reg_list_does_not_eagerly_stringify_and_passes_core_unit():
    class Register:
        name = "X0"
        unit = "CPU"
        core = 0
        value = 0xFFFFFFFFFFFFFFFF
        fvalue = None

        def __str__(self):
            raise OverflowError("int too large to convert")

    class RegisterService:
        def __init__(self):
            self.kwargs = None

        def read_all(self, **kwargs):
            self.kwargs = kwargs
            return [Register()]

    service = RegisterService()
    result = core.h_reg_list(
        SimpleNamespace(register=service),
        SimpleNamespace(core=0, unit="CPU", contains=None),
    )
    assert service.kwargs == {"core": 0, "unit": "CPU"}
    assert result[0]["value"] == 0xFFFFFFFFFFFFFFFF


def test_mem_read_count_uses_repeated_scalar_reads():
    class Address:
        def __init__(self, access=None, value=None):
            self.access = access
            self.value = value

        def __str__(self):
            return f"{self.access + ':' if self.access else ''}0x{self.value:x}"

    class AddressService:
        def from_string(self, text):
            access, value = (text.split(":", 1) if ":" in text else (None, text))
            return Address(access, int(value, 0))

        def __call__(self, *, access=None, value=None):
            return Address(access, value)

    class MemoryService:
        def __init__(self):
            self.addresses = []

        def read_uint64(self, address, *, byteorder=None, width=8):
            self.addresses.append(address.value)
            return address.value

    memory = MemoryService()
    dbg = SimpleNamespace(address=AddressService(), memory=memory)
    result = core.h_mem_read(
        dbg,
        SimpleNamespace(
            address="0x123456780abcdef",
            access=None,
            type="u64",
            count=2,
            byteorder=None,
        ),
    )
    assert memory.addresses == [0x123456780ABCDEF, 0x123456780ABCDF7]
    assert result["value"] == memory.addresses


def test_mem_dump_passes_keyword_only_length():
    class Address:
        access = None
        value = 0x1000

        def __str__(self):
            return "0x1000"

    class MemoryService:
        def read(self, address, *, length, width=None):
            assert address.value == 0x1000
            assert length == 4
            return b"\x01\x02\x03\x04"

    dbg = SimpleNamespace(
        address=SimpleNamespace(from_string=lambda _text: Address()),
        memory=MemoryService(),
    )
    result = core.h_mem_dump(dbg, SimpleNamespace(address="0x1000", access=None, length=4))
    assert result["hex"] == "01020304"


def test_target_info_discovers_runtime_capabilities():
    mapping = {
        "CPU()": "CORTEXA78",
        "CPUFAMILY()": "ARM",
        "CPUCOREVERSION()": "v8.2",
        "CPUIS64BIT()": True,
        "CONFIGNUMBER()": 4,
        "SYStem.BIGENDIAN()": False,
        "STATE.RUN()": False,
        "STATE.HALT()": True,
        "ARM64()": True,
    }
    result = runtime.h_target_info(SimpleNamespace(fnc=lambda expression: mapping[expression]), SimpleNamespace())
    assert result["architecture"] == "AArch64"
    assert result["configured_cores"] == 4
    assert result["state"] == "halted"
    assert result["endianness"] == "little"


def test_bp_enums_come_from_runtime_breakpoint_class():
    class Breakpoint:
        class Type(enum.IntEnum):
            PROGRAM = 1
            READ = 2

        class Impl(enum.IntEnum):
            AUTO = 0
            ONCHIP = 2

        class Action(enum.IntEnum):
            NONE = 0
            STOP = 1

    result = runtime.h_bp_enums(SimpleNamespace(breakpoint=lambda: Breakpoint()), SimpleNamespace())
    assert result["type"][0] == {"name": "PROGRAM", "value": 1}
    assert result["impl"][1]["name"] == "ONCHIP"


def test_breakpoint_mutation_uses_breakpoint_object_methods():
    class Breakpoint:
        def __init__(self):
            self.deleted = False
            self.enabled = None

        def delete(self):
            self.deleted = True

        def enable(self):
            self.enabled = True

        def disable(self):
            self.enabled = False

    bp = Breakpoint()
    dbg = SimpleNamespace(breakpoint=SimpleNamespace(list=lambda: [bp]))
    core.h_bp_delete(dbg, SimpleNamespace(index=0))
    core.h_bp_enable(dbg, SimpleNamespace(index=0))
    core.h_bp_disable(dbg, SimpleNamespace(index=0))
    assert bp.deleted is True
    assert bp.enabled is False


def test_layered_profile_config_and_cli_override(tmp_path: Path, monkeypatch):
    _isolated_config(tmp_path, monkeypatch)
    user = tmp_path / "user-config" / "trace32-cli"
    user.mkdir(parents=True)
    (user / "config.toml").write_text(
        'default = "app"\n\n[connection]\nprotocol = "TCP"\ntimeout = 20\n\n'
        '[profiles.app]\nhost = "10.0.0.1"\nport = 20001\n',
        encoding="utf-8",
    )
    project = tmp_path / ".trace32"
    project.mkdir()
    (project / "config.toml").write_text(
        '[profiles.app]\nhost = "127.0.0.1"\nport = 21001\n',
        encoding="utf-8",
    )

    args = build_parser().parse_args(["profile", "current"])
    runtime_config, meta = resolve_runtime(args)
    assert runtime_config["host"] == "127.0.0.1"
    assert runtime_config["port"] == 21001
    assert runtime_config["timeout"] == 20
    assert meta["sources"]["host"].endswith(".trace32/config.toml")
    assert [item["layer"] for item in meta["files"]] == ["user", "project"]

    args = build_parser().parse_args(
        ["--host", "10.0.0.3", "--port", "20003", "profile", "current"]
    )
    runtime_config, _ = resolve_runtime(args)
    assert runtime_config["host"] == "10.0.0.3"
    assert runtime_config["port"] == 20003


def test_profile_commands_and_skill_install(tmp_path: Path, monkeypatch, capsys):
    _isolated_config(tmp_path, monkeypatch)
    config_dir = tmp_path / ".trace32"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        'default = "app"\n\n[profiles.app]\nhost = "localhost"\nport = 20001\n\n'
        '[profiles.safety]\nhost = "localhost"\nport = 20002\n',
        encoding="utf-8",
    )
    assert main(["--json", "profile", "list"]) == 0
    assert [item["name"] for item in json.loads(capsys.readouterr().out)["data"]] == ["app", "safety"]
    root = tmp_path / "skills"
    assert main(["--json", "skill", "install", "--dir", str(root)]) == 0
    capsys.readouterr()
    assert (root / "t32" / "SKILL.md").is_file()
    assert main(["--json", "skill", "uninstall", "--dir", str(root)]) == 0
    assert not (root / "t32").exists()
