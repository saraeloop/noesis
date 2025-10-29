from __future__ import annotations

import json

import noesis as ns
from noesis import cli


def test_cli_events_help_mentions_insight(capsys):
    code = cli.main(["events", "-h"])
    out = capsys.readouterr().out
    assert code == 0
    assert "insight" in out


def test_cli_events_phase_insight_json(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    ns.set(runs_dir=str(runs_dir))

    episode_id = ns.run(task="CLI insight test", intuition=False)
    code = cli.main(["events", episode_id, "--phase", "insight", "-j"])
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
    code = cli.main(["insight", episode_id, "-j"])
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
