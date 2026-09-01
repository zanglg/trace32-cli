import json
from pathlib import Path

from trace32_cli.config import config_locations, project_root, resolve_runtime
from trace32_cli.entry import build_parser, main


def _isolate_user_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user-config"))


def test_nearest_project_config_wins_over_git_root(tmp_path: Path, monkeypatch):
    _isolate_user_config(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    project = repo / "product-a"
    workdir = project / "firmware" / "src"
    (project / ".trace32").mkdir(parents=True)
    workdir.mkdir(parents=True)
    (project / ".trace32" / "config.toml").write_text(
        'default = "app"\n\n[profiles.app]\nhost = "127.0.0.1"\nport = 20002\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(workdir)

    assert project_root() == project.resolve()
    locations = config_locations()
    assert locations == {
        "user": str(tmp_path / "user-config" / "trace32-cli" / "config.toml"),
        "project": str(project / ".trace32" / "config.toml"),
    }

    args = build_parser().parse_args(["profile", "current"])
    runtime, meta = resolve_runtime(args)
    assert runtime["profile"] == "app"
    assert runtime["host"] == "127.0.0.1"
    assert runtime["port"] == 20002
    assert meta["project_root"] == str(project.resolve())
    assert [item["layer"] for item in meta["files"]] == ["project"]


def test_bare_t32_shows_resolved_project_configuration(tmp_path: Path, monkeypatch, capsys):
    _isolate_user_config(tmp_path, monkeypatch)
    project = tmp_path / "project"
    workdir = project / "subdir"
    (project / ".trace32").mkdir(parents=True)
    workdir.mkdir()
    config = project / ".trace32" / "config.toml"
    config.write_text(
        'default = "app"\n\n[profiles.app]\nhost = "127.0.0.1"\nport = 21000\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(workdir)

    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Resolved configuration:" in output
    assert f"project root: {project.resolve()}" in output
    assert "profile:      app" in output
    assert "endpoint:     127.0.0.1:21000/TCP" in output
    assert str(config) in output


def test_capabilities_exposes_two_persistent_config_levels(tmp_path: Path, monkeypatch, capsys):
    _isolate_user_config(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert main(["--json", "capabilities"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert set(data["configuration"]["files"]) == {"user", "project"}
    assert "project local config" not in data["configuration"]["precedence"]
    assert data["configuration"]["precedence"][:4] == [
        "explicit CLI options",
        "--config file",
        "project config",
        "user config",
    ]
