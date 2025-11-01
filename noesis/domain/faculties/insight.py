"""
Domain insight helpers compute metrics from episode traces.

These functions are pure and framework agnostic so they can be reused across
application services and adapters without introducing infrastructure coupling.
"""

from __future__ import annotations

from collections import Counter
from math import ceil
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = ["compute_metrics"]


def _first_event_time(events: Iterable[Dict[str, Any]], phase: str) -> Optional[str]:
    for event in events:
        if event.get("phase") == phase:
            return event.get("timestamp")
    return None


try:
    from dateutil import parser as _parser  # type: ignore

    def _parse_iso(value: str):
        return _parser.isoparse(value)

except Exception:  # pragma: no cover - optional dependency
    from datetime import datetime

    def _parse_iso(value: str):
        # Minimal fallback: handle strict ISO 8601; map 'Z' → '+00:00'
        return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ms_between(start: Optional[str], finish: Optional[str]) -> Optional[int]:
    if not start or not finish:
        return None
    try:
        begin = _parse_iso(start)
        end = _parse_iso(finish)
        delta_ms = (end - begin).total_seconds() * 1000
        if delta_ms <= 0:
            return 0
        return int(ceil(delta_ms))
    except Exception:  # pragma: no cover - defensive guard
        return None


def _success_from_events(events: List[Dict[str, Any]]) -> int:
    for event in reversed(events):
        if event.get("phase") == "terminate":
            status = (event.get("payload") or {}).get("status")
            return 1 if status == "ok" else 0
    return 0


def compute_metrics(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute roll-up metrics from an episode summary + event stream."""
    direction_events = [event for event in events if event.get("phase") == "direction"]
    plan_events = [event for event in events if event.get("phase") == "plan"]
    reflect_events = [event for event in events if event.get("phase") == "reflect"]
    act_events = [event for event in events if event.get("phase") == "act"]
    interpret_events = [event for event in events if event.get("phase") == "interpret"]

    applied = [
        event
        for event in direction_events
        if event.get("payload", {}).get("applied")
        and event.get("payload", {}).get("status") != "blocked"
    ]
    vetoed = [
        event
        for event in direction_events
        if event.get("payload", {}).get("status") == "blocked"
        or event.get("payload", {}).get("reason") == "veto"
    ]

    total_dir = max(len(direction_events), 1)
    direction_applied_rate = len(applied) / total_dir
    veto_rate: Optional[float] = None
    if direction_events:
        veto_rate = len(vetoed) / len(direction_events)

    reasons = [event.get("payload", {}).get("reason", "unknown") for event in direction_events]
    top_reasons: List[Tuple[str, int]] = Counter(reasons).most_common(5)

    t_start = _first_event_time(events, "start")
    t_first_act = _first_event_time(act_events, "act")
    first_action_latency_ms = _ms_between(t_start, t_first_act)

    t_veto = _first_event_time(vetoed, "direction")
    time_to_veto_ms = _ms_between(t_start, t_veto)

    conf_applied = [float(event["payload"].get("confidence", 0.0)) for event in applied]
    conf_rejected = [
        float(event["payload"].get("confidence", 0.0))
        for event in direction_events
        if event not in applied
    ]
    alignment = (
        (mean(conf_applied) if conf_applied else 0.0)
        - (mean(conf_rejected) if conf_rejected else 0.0)
    )

    buckets = [0] * 10
    for event in direction_events:
        confidence = float(event["payload"].get("confidence", 0.0))
        index = min(max(int(confidence * 10), 0), 9)  # confidence=1.0 → bucket 9
        buckets[index] += 1

    ideal_steps = summary.get("metrics", {}).get("ideal_steps", 0)

    metrics: Dict[str, Any] = {
        "success": _success_from_events(events),
        "plan_count": len(plan_events),
        "reflect_count": len(reflect_events),
        "ideal_steps": ideal_steps,
        "direction_events": len(direction_events),
        "direction_applied": len(applied),
        "direction_vetoed": len(vetoed),
        "direction_applied_rate": direction_applied_rate,
        "top_reasons": top_reasons,
        "latencies": {
            "first_action_ms": first_action_latency_ms,
            "time_to_veto_ms": time_to_veto_ms,
        },
        "policy_confidence_histogram": buckets,
        "alignment": alignment,
        "act_count": len(act_events),
        "steps": len(act_events),
        "interpret_count": len(interpret_events),
        "experimental": {
            "action_efficiency": None,
            "coherence": None,
            "tool_correctness": None,
            "intuition_alignment": None,
            "learn_kinds": {},
        },
        "learn_proposals": 0,
        "learn_applied": 0,
    }
    if veto_rate is not None and direction_events:
        metrics["veto_rate"] = veto_rate

    return _finalize_metrics(metrics)


def _finalize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize metric payload before it is persisted/emitted."""
    act_count = metrics.get("act_count", metrics.get("steps", 0))
    metrics["act_count"] = act_count
    metrics["steps"] = act_count

    if metrics.get("direction_events", 0) == 0:
        metrics.pop("veto_rate", None)
        metrics["direction_applied_rate"] = 0.0

    latencies = metrics.get("latencies", {}) or {}
    latencies = {key: value for key, value in latencies.items() if value is not None}
    if latencies:
        metrics["latencies"] = latencies
    else:
        metrics.pop("latencies", None)

    experimental = metrics.get("experimental") or {}
    experimental = {key: value for key, value in experimental.items() if value is not None}
    if experimental.get("learn_kinds") == {}:
        experimental.pop("learn_kinds", None)
    if experimental:
        metrics["experimental"] = experimental
    else:
        metrics.pop("experimental", None)

    return metrics
