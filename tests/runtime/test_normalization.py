from __future__ import annotations

from noesis.runtime.normalization import compute_summary_metrics_from_events


def test_compute_summary_metrics_sets_phase_ms_none_when_timings_unavailable() -> None:
    summary_metrics, insight_metrics = compute_summary_metrics_from_events(
        [
            {
                "phase": "start",
                "payload": {"task": "no timings"},
                "evidence_ids": [],
            }
        ]
    )

    assert insight_metrics.to_mapping().get("phase_ms") is None
    assert summary_metrics.get("phase_ms") is None
