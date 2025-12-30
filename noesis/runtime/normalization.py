"""
Normalization helpers for artifact emission.

Keeps normalization logic centralized so artifacts stay consistent
across emitters, summary computation, and state persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from noesis.domain.faculties.insight import InsightMetrics, build_insight_metrics, compute_metrics
__all__ = [
    "UsingNormalization",
    "normalize_using",
    "compute_summary_metrics_from_events",
]


@dataclass(frozen=True, slots=True)
class UsingNormalization:
    """Normalized representation of a `using` label."""

    display: str
    using_kind: str | None = None
    using_id: str | None = None


def normalize_using(value: str | None) -> UsingNormalization | None:
    """Return the canonical `using` label plus optional metadata."""
    if value is None:
        return None
    raw = str(value)
    if raw.startswith("adapter:"):
        display = raw.split("adapter:", 1)[1]
        return UsingNormalization(display=display, using_kind="adapter", using_id=raw)
    return UsingNormalization(display=raw)


def compute_summary_metrics_from_events(
    events: Iterable[Dict[str, Any]],
) -> Tuple[Dict[str, Any], InsightMetrics]:
    """Compute canonical summary metrics and aligned insight metrics from events."""
    event_list = list(events)
    summary_metrics = compute_metrics({}, event_list)
    insight_metrics = build_insight_metrics(event_list, summary_metrics)
    summary_metrics["plan_adherence"] = insight_metrics.plan_adherence
    summary_metrics["tool_coverage"] = insight_metrics.tool_coverage
    summary_metrics["veto_count"] = insight_metrics.veto_count
    summary_metrics["success"] = insight_metrics.success
    return summary_metrics, insight_metrics
