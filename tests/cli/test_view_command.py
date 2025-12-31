from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

import pytest

from noesis.cli.commands.view import COMMAND as VIEW_COMMAND
from noesis.cli.context import CLIContext, GlobalOptions


class _Renderer:
    def __init__(self) -> None:
        self.view = None
        self.lines: list[str] = []

    def banner(self, text: str) -> None:
        self.lines.append(text)

    def echo(self, text: str) -> None:
        self.lines.append(text)

    def print_viewer(self, view, *, grep: str | None = None) -> None:
        self.view = view

    def json(self, data) -> None:
        self.view = data

    def print_events(self, events) -> None:
        self.lines.extend([str(event) for event in events])


def _make_context(runs_dir) -> CLIContext:
    snapshot = SimpleNamespace(runs_dir=runs_dir)
    runtime_ctx = SimpleNamespace(list_ports=lambda: {})
    return CLIContext(
        options=GlobalOptions(),
        config={},
        isatty=False,
        version="test",
        runtime_context=runtime_ctx,
        config_snapshot=snapshot,
        session=None,
    )


def test_view_uses_remote_when_run_dir_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    ctx = _make_context(runs_dir)

    summary = {
        "episode_id": "ep_remote",
        "started_at": "2025-01-01T00:00:00+00:00",
        "duration_sec": 1.2,
        "flags": {"mode": "off", "using": "core.meta"},
        "metrics": {"success": 1, "plan_adherence": 1.0, "veto_count": 0, "tool_coverage": 0.5},
    }
    events = [
        {
            "id": "evt-1",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "episode_id": "ep_remote",
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": "Remote task"},
        },
        {
            "id": "evt-2",
            "timestamp": "2025-01-01T00:00:01+00:00",
            "episode_id": "ep_remote",
            "agent_id": "system",
            "phase": "terminate",
            "payload": {"status": "ok"},
        },
    ]

    monkeypatch.setattr("noesis.summary.read", lambda episode_id, context=None: summary)
    monkeypatch.setattr("noesis.events.read", lambda episode_id, context=None, stream=False: events)

    args = Namespace(
        target="ep_remote",
        pretty=False,
        json=False,
        events=False,
        grep=None,
        limit=50,
        schema="latest",
        fail_on_invalid=False,
        open=False,
    )
    renderer = _Renderer()
    assert VIEW_COMMAND.run(args, ctx, renderer) == 0
    assert renderer.view is not None
    assert renderer.view.header.episode_id == "ep_remote"
    assert renderer.view.timeline_rows
