from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from noesis.cli.render.plain import PlainRenderer
from noesis.cli.view_models import build_episode_dashboard


def test_plain_viewer_output_matches_fixture(demo_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(demo_run.parent)

    view = build_episode_dashboard(demo_run, validate=True)
    assert view.validation_issues == []

    renderer = PlainRenderer()
    buffer = StringIO()
    with redirect_stdout(buffer):
        renderer.print_viewer(view)
    output_lines = buffer.getvalue().splitlines()

    normalized = [line.rstrip() for line in output_lines]
    assert normalized[0].startswith("Episode ep_20251104_155501_805857_c5f4_s0")
    assert any("planner=off" in line for line in normalized)
    assert any("using=core.meta" in line for line in normalized)

    assert "KPIs" in normalized
    assert "Execution Map" in normalized
    assert "Verification" in normalized
    assert any("plan_adherence" in line and "0.00" in line for line in normalized)
    assert any("veto_count" in line and "1" in line for line in normalized)

    borders = [line for line in normalized if line.startswith("+") and line.endswith("+")]
    assert borders, "expected table borders in plain output"

    timeline_header = [
        line for line in normalized if line.startswith("|") and "Δt" in line and "summary" in line
    ]
    assert timeline_header, "expected timeline table header in plain output"

    timeline = [line for line in normalized if line.strip().startswith("|")]

    def has_phase(phase: str, needle: str | None = None) -> bool:
        for line in timeline:
            if f" {phase:<12} " in line:
                if needle is None or needle in line:
                    return True
        return False

    assert has_phase("start", "Danger operation")
    assert has_phase("governance", "veto")
    assert has_phase("direction", "blocked")
    assert has_phase("terminate", "Task flagged as dangerous")
