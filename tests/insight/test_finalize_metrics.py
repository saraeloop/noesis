from __future__ import annotations

from noesis.domain.faculties.insight import build_insight_metrics


def test_build_insight_metrics_respects_events() -> None:
    events = [
        {"phase": "observe", "metrics": {"duration_ms": 120}},
        {"phase": "interpret", "metrics": {"duration_ms": 240}},
        {"phase": "plan", "metrics": {"duration_ms": 300}},
        {"phase": "direction", "payload": {"status": "applied"}},
        {"phase": "direction", "payload": {"status": "blocked"}},
        {"phase": "governance", "payload": {"decision": "veto", "mode": "enforce", "enforced": True}},
        {
            "phase": "act",
            "metrics": {"duration_ms": 540},
            "payload": {"tool": "adapter:core.minimal"},
        },
        {"phase": "reflect", "metrics": {"duration_ms": 200}},
    ]
    summary_metrics = {
        "success": 1,
        "direction_events": 2,
        "plan_count": 1,
        "act_count": 1,
    }

    insight = build_insight_metrics(events, summary_metrics).to_mapping()

    assert insight["veto_count"] == 1
    assert insight["would_veto_count"] == 0
    assert insight["plan_revisions"] == 1
    assert insight["tool_coverage"] == 1.0
    assert insight["success"] is True
    assert insight["branching_factor"] == 2.0
    assert insight["plan_adherence"] == 1.0
    assert insight["phase_ms"]["act"] == 540
