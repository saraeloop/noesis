from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import noesis

from noesis.cli.render.plain import PlainRenderer
from noesis.cli.viewer import load_episode_view


def test_plain_viewer_output_matches_fixture() -> None:
    run_dir = Path("runs/demo/ep_20251104_155501_805857_c5f4_s0")
    assert run_dir.exists(), "expected demo run directory to exist for snapshot test"

    view = load_episode_view(str(run_dir), ns=noesis, runtime_context=None)

    renderer = PlainRenderer()
    buffer = StringIO()
    with redirect_stdout(buffer):
        renderer.print_viewer(view)
    output_lines = buffer.getvalue().splitlines()

    normalized = [line.rstrip() for line in output_lines]
    assert normalized[0] == "Episode"
    assert "  planner_mode: off" in normalized
    assert "  intuition   : off" in normalized
    assert any("policies" in line and "governance.rules" in line for line in normalized)

    assert "KPIs" in normalized
    assert any("plan_adherence" in line and "0.0" in line for line in normalized)
    assert any("veto_count" in line and "1" in line for line in normalized)

    assert "Governance" in normalized
    assert any("decision" in line and "veto" in line for line in normalized)
    assert any("rule_id" in line and "rules.veto.danger" in line for line in normalized)

    timeline = [line for line in normalized if line.strip().startswith("[")]

    def has_phase(phase: str, needle: str | None = None) -> bool:
        for line in timeline:
            if f" {phase:<10} " in line:
                if needle is None or needle in line:
                    return True
        return False

    assert has_phase("start", "Danger operation")
    assert has_phase("governance", "veto")
    assert has_phase("direction", "blocked")
    assert has_phase("act", "blocked")
    assert has_phase("reflect")
    assert has_phase("terminate", "Task flagged as dangerous")
