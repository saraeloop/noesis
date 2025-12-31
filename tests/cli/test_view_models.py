from __future__ import annotations

from pathlib import Path

from noesis.cli.view_models import build_episode_dashboard


def _parse_dt(dt_str: str) -> float:
    normalized = dt_str.strip().lstrip("+").rstrip("s")
    return float(normalized)


def test_build_episode_dashboard_view_model(demo_run: Path) -> None:
    vm = build_episode_dashboard(demo_run, limit_timeline=3, validate=True)
    assert vm.header.episode_id
    assert vm.header.status_label
    assert vm.chips.using == "core.meta"
    assert vm.kpis.veto_count == 1
    assert len(vm.timeline_rows) == 3

    deltas = [_parse_dt(row.dt_str) for row in vm.timeline_rows]
    assert deltas == sorted(deltas)
