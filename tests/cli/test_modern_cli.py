from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from noesis.cli import main as cli_main
from noesis.cli.context import GlobalOptions


class _DummySummary:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self, episode_id: str, context=None):  # noqa: D401 - test helper
        return dict(self._payload)


class _DummyEvents:
    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def read(self, episode_id: str, context=None, stream: bool = False):
        return list(self._events)


class _DummyNS:
    def __init__(self, summary: dict, events: list[dict]) -> None:
        self.summary = _DummySummary(summary)
        self.events = _DummyEvents(events)

    def run(self, *, task: str, context=None, workspace=None, verify=None):
        return "ep_test"


def _fake_context(summary: dict, events: list[dict], runs_dir: Path):
    ns = _DummyNS(summary, events)
    config_snapshot = SimpleNamespace(runs_dir=runs_dir, to_mapping=lambda: {})
    runtime_context = SimpleNamespace()
    return SimpleNamespace(
        options=GlobalOptions(),
        config={},
        isatty=False,
        version="1.0.0",
        runtime_context=runtime_context,
        config_snapshot=config_snapshot,
        session=None,
        ns=ns,
    )


def test_cli_run_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path) -> None:
    summary = {
        "episode_id": "ep_test",
        "task": "Run task",
        "started_at": "2025-01-01T00:00:00Z",
        "duration_sec": 1.2,
        "adapter_result": "success",
        "outcome": "success_unverified",
        "verification": {"provided": False, "passed": None, "assertions": [], "workspace_diff": None, "error": None},
        "flags": {"mode": "off"},
        "metrics": {"success": 1, "plan_adherence": 1.0, "veto_count": 0, "tool_coverage": 1.0},
    }
    events = []
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(
        "noesis.cli.__main__.build_context",
        lambda options, port_specs: _fake_context(summary, events, tmp_path),
    )
    code = cli_main(["run", "Run task"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Agent" in out
    assert "Verify" in out
    assert "Outcome" in out
    assert "noesis view ep_test" in out


def test_cli_view_compact_and_verbose(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path) -> None:
    summary = {
        "episode_id": "ep_test",
        "task": "View task",
        "started_at": "2025-01-01T00:00:00Z",
        "duration_sec": 2.4,
        "adapter_result": "success",
        "outcome": "success_unverified",
        "verification": {"provided": False, "passed": None, "assertions": [], "workspace_diff": None, "error": None},
        "flags": {"mode": "off"},
        "metrics": {"success": 1, "plan_adherence": 1.0, "veto_count": 0, "tool_coverage": 1.0},
    }
    events = [
        {"timestamp": "2025-01-01T00:00:00Z", "episode_id": "ep_test", "phase": "start", "payload": {"task": "View task"}},
        {"timestamp": "2025-01-01T00:00:01Z", "episode_id": "ep_test", "phase": "terminate", "payload": {"status": "ok"}},
    ]
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(
        "noesis.cli.__main__.build_context",
        lambda options, port_specs: _fake_context(summary, events, tmp_path),
    )

    code = cli_main(["view", "ep_test"])
    out = capsys.readouterr().out
    assert code == 0
    assert "KPIs" not in out
    assert "Timeline" not in out
    assert "Summary" in out
    assert "Execution:" in out
    assert "Changed Files" not in out

    code = cli_main(["view", "ep_test", "--verbose"])
    out = capsys.readouterr().out
    assert code == 0
    assert "KPIs" in out
    assert "Timeline" in out
