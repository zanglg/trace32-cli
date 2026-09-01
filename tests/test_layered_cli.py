import json

from trace32_cli.entry import build_parser, main


def test_layered_parser_exposes_debugger_domains():
    parser = build_parser()
    commands = [
        ["exec", "wait"],
        ["exec", "next"],
        ["exec", "finish"],
        ["exec", "run-to", "main", "--kind", "symbol"],
        ["context", "current"],
        ["watch", "add", "0x1000", "--access", "write"],
        ["expr", "eval", "foo->state"],
        ["type", "describe", "foo"],
        ["source", "current"],
        ["insn", "current"],
        ["stack", "backtrace"],
        ["frame", "up"],
        ["program", "list"],
    ]
    for argv in commands:
        args = parser.parse_args(argv)
        assert callable(args.handler)


def test_layered_capabilities_describe_layer_boundaries(capsys):
    assert main(["--json", "capabilities"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    model = data["debugger_model"]
    assert "GDB-inspired" in model["layer1"]
    assert "PyRCL-inspired" in model["layer0"]
    assert "opaque strings" in model["architecture_registers"]
    assert model["location"] == ["address", "symbol", "source"]


def test_schema_marks_new_mutating_commands(capsys):
    assert main(["--json", "schema"]) == 0
    commands = json.loads(capsys.readouterr().out)["data"]["commands"]
    assert commands["exec next"]["target_mutating"] is True
    assert commands["watch add"]["target_mutating"] is True
    assert commands["expr assign"]["target_mutating"] is True
    assert commands["source current"]["target_mutating"] is False
