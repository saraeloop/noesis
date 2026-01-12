from __future__ import annotations

from pathlib import Path

from noesis.cli.view_models import build_episode_dashboard, build_episode_dashboard_from_payloads


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
    assert vm.execution_map.observe.status
    assert vm.execution_map.outcome.status

    deltas = [_parse_dt(row.dt_str) for row in vm.timeline_rows]
    assert deltas == sorted(deltas)


def test_view_model_verification_section() -> None:
    summary = {
        "episode_id": "ep_test",
        "started_at": "2025-01-01T00:00:00Z",
        "duration_sec": 1.0,
        "flags": {"mode": "off"},
        "metrics": {"success": 1, "plan_adherence": 1.0, "veto_count": 0, "tool_coverage": 1.0},
        "adapter_result": "success",
        "outcome": "success",
        "verification": {
            "provided": True,
            "passed": True,
            "assertions": [
                {"name": "file_exists", "target": "config.yaml", "passed": True, "reason": None}
            ],
            "workspace_diff": {"added": ["config.yaml"], "modified": [], "deleted": []},
            "error": None,
        },
    }
    events = [
        {
            "id": "evt-1",
            "timestamp": "2025-01-01T00:00:00Z",
            "episode_id": "ep_test",
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": "Test"},
        },
        {
            "id": "evt-2",
            "timestamp": "2025-01-01T00:00:01Z",
            "episode_id": "ep_test",
            "agent_id": "system",
            "phase": "terminate",
            "payload": {"status": "ok"},
        },
    ]
    vm = build_episode_dashboard_from_payloads(summary=summary, events=events, episode_id="ep_test")
    assert vm.verification.passed is True
    assert vm.execution_map.verify.status == "PASSED"
