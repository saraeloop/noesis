"""
Insight layer for Noēsis.

Responsible for reflection, interpreting what happened after execution.
Insight transforms traces and summaries into measurable understanding:
patterns, success rates, and signals of alignment or drift.

This layer closes the cognitive loop by turning experience into knowledge.
"""

from __future__ import annotations

from collections import Counter
from math import ceil
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = ["compute_metrics"]


def _first_event_time(events: Iterable[Dict[str, Any]], phase: str) -> Optional[str]:
    for e in events:
        if e.get("phase") == phase:
            return e.get("timestamp")
    return None


# Optional robust ISO8601 parsing (fallback to stdlib if dateutil missing)
try:
    from dateutil import parser as _p  # type: ignore

    def _parse_iso(s: str):
        return _p.isoparse(s)

except Exception:
    from datetime import datetime

    def _parse_iso(s: str):
        # Minimal fallback: handle strict ISO 8601; map 'Z' → '+00:00'
        return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _ms_between(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        t0 = _parse_iso(a)
        t1 = _parse_iso(b)
        delta_ms = (t1 - t0).total_seconds() * 1000
        if delta_ms <= 0:
            return 0
        return int(ceil(delta_ms))
    except Exception:
        return None


def compute_metrics(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute roll-up metrics from an episode summary + event stream."""
    direction_events = [e for e in events if e.get("phase") == "direction"]

    applied = [
        e for e in direction_events
        if e.get("payload", {}).get("applied")
        and e.get("payload", {}).get("status") != "blocked"
    ]
    vetoed = [
        e for e in direction_events
        if e.get("payload", {}).get("status") == "blocked"
        or e.get("payload", {}).get("reason") == "veto"
    ]

    # Rates
    total_dir = len(direction_events) or 1  # guard
    direction_applied_rate = len(applied) / total_dir
    veto_rate = len(vetoed) / total_dir

    # Top reasons
    reasons = [e.get("payload", {}).get("reason", "unknown") for e in direction_events]
    top_reasons: List[Tuple[str, int]] = Counter(reasons).most_common(5)

    # Latencies
    t_start = _first_event_time(events, "start")
    t_first_dir = _first_event_time(direction_events, "direction")
    first_action_latency_ms = _ms_between(t_start, t_first_dir)

    t_veto = _first_event_time(vetoed, "direction")
    time_to_veto_ms = _ms_between(t_start, t_veto)

    # Confidence alignment
    conf_applied = [float(e["payload"].get("confidence", 0.0)) for e in applied]
    conf_rejected = [
        float(e["payload"].get("confidence", 0.0))
        for e in direction_events
        if e not in applied
    ]
    alignment = (
        (mean(conf_applied) if conf_applied else 0.0)
        - (mean(conf_rejected) if conf_rejected else 0.0)
    )

    # Confidence histogram (10 buckets: [0.0, 1.0))
    buckets = [0] * 10
    for e in direction_events:
        c = float(e["payload"].get("confidence", 0.0))
        idx = min(max(int(c * 10), 0), 9)  # c=1.0 → bucket 9
        buckets[idx] += 1

    base_steps = len(events)
    ideal_steps = summary.get("metrics", {}).get("ideal_steps", 0)

    return {
        "success": summary.get("metrics", {}).get("success", 0),
        "steps": base_steps,
        "ideal_steps": ideal_steps,
        "action_efficiency": 0.0,            # TBD (when act-phase semantics land)
        "tool_correctness": 0.0,             # TBD
        "coherence": 0.0,                    # TBD
        "intuition_alignment": 0.0,          # keep placeholder for now
        "direction_events": len(direction_events),
        "direction_applied": len(applied),
        "direction_vetoed": len(vetoed),
        "direction_applied_rate": direction_applied_rate,
        "veto_rate": veto_rate,
        "top_reasons": top_reasons,
        "first_action_latency_ms": first_action_latency_ms,
        "time_to_veto_ms": time_to_veto_ms,
        "policy_confidence_histogram": buckets,
        "alignment": alignment,
    }
