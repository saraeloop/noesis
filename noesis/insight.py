"""Curated re-exports for insight metrics.

Most users read InsightMetrics from summary.json. These helpers are for
computing custom roll-ups or parsing artifact payloads.
"""

from noesis.domain.faculties.insight import (
    InsightMetrics,
    build_insight_metrics,
    compute_metrics,
)

__all__ = [
    "InsightMetrics",
    "build_insight_metrics",
    "compute_metrics",
]

