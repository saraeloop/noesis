from __future__ import annotations

import json

import noesis as ns
from noesis.cli import main as cli_main
from noesis.runtime.paths import resolve_noesis_paths
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION


def test_cli_events_help_mentions_insight(capsys):
    code = cli_main(["events", "-h"])
    out = capsys.readouterr().out
    assert code == 0
    assert "insight" in out


def test_cli_events_phase_insight_json(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    ns.set(runs_dir=str(runs_dir))

    episode_id = ns.run(task="CLI insight test", intuition=False)
    code = cli_main(["events", episode_id, "--phase", "insight", "-j"])
    output = capsys.readouterr().out.strip()

    assert code == 0
    assert output
    decoder = json.JSONDecoder()
    idx = 0
    parsed = 0
    while idx < len(output):
        while idx < len(output) and output[idx].isspace():
            idx += 1
        if idx >= len(output):
            break
        obj, idx = decoder.raw_decode(output, idx)
        parsed += 1
        assert obj.get("phase") == "insight"
    assert parsed >= 1


def test_cli_insight_command(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    ns.set(runs_dir=str(runs_dir))

    episode_id = ns.run(task="CLI insight shortcut", intuition=False)
    code = cli_main(["insight", episode_id, "-j"])
    output = capsys.readouterr().out.strip()

    assert code == 0
    assert output
    decoder = json.JSONDecoder()
    idx = 0
    found = 0
    while idx < len(output):
        while idx < len(output) and output[idx].isspace():
            idx += 1
        if idx >= len(output):
            break
        obj, idx = decoder.raw_decode(output, idx)
        found += 1
        assert obj.get("phase") == "insight"
    assert found >= 1


def test_cli_validate_ports_json(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    ns.set(runs_dir=str(runs_dir))

    code = cli_main(["validate-ports", "--json"])
    output = capsys.readouterr().out.strip()

    assert code == 0
    payload = json.loads(output)
    assert "ports" in payload
    assert payload["ports"]["config"].startswith("config/")


def test_cli_diagnostics_json(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    learn_home = tmp_path / "learn"
    learn_home.mkdir()

    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_home))
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    layout.episodes_dir.mkdir(parents=True, exist_ok=True)

    code = cli_main(["diagnostics", "--json"])
    output = capsys.readouterr().out.strip()

    assert code == 0
    assert output

    payload = json.loads(output)
    assert payload["summary_schema_version"] == SUMMARY_SCHEMA_VERSION
    assert payload["selected_checks"] == ["all"]
    assert isinstance(payload["timestamp"], int)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["runs_dir"]["status"] == "ok"
    assert checks["learn_home"]["status"] == "ok"
    assert checks["latest_summary"]["status"] == "ok"


def test_cli_diagnostics_strict_warn(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    learn_home = tmp_path / "learn"

    ns.set(
        runs_dir=str(runs_dir),
        learn_home=str(learn_home),
    )
    # remove learn_home after configuration to trigger warn
    learn_home.rmdir()

    code = cli_main(["diagnostics", "--strict"])
    capsys.readouterr()
    assert code == 1


def test_cli_diagnostics_checks_filter(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    learn_home = tmp_path / "learn"
    learn_home.mkdir()

    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_home))
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    layout.episodes_dir.mkdir(parents=True, exist_ok=True)

    code = cli_main(["diagnostics", "--json", "--checks", "runs_dir"])
    output = capsys.readouterr().out.strip()

    assert code == 0

    payload = json.loads(output)
    assert payload["selected_checks"] == ["runs_dir"]
    check_names = {item["name"] for item in payload["checks"]}
    assert "runs_dir" in check_names
    assert "learn_home" not in check_names
