"""
Domain insight helpers compute metrics from episode traces.

These functions are pure and framework agnostic so they can be reused across
application services and adapters without introducing infrastructure coupling.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import ceil
from statistics import mean
from typing import Any, ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .versioning import current_version, is_compatible

__all__ = ["InsightMetrics", "compute_metrics", "build_insight_metrics"]


@dataclass(frozen=True, slots=True)
class InsightMetrics:
    """Canonical insight payload persisted into summary artifacts."""

    schema_version: ClassVar[str] = current_version("insight")
    phase_ms: Mapping[str, Optional[int]] = field(default_factory=dict)
    veto_count: int = 0
    would_veto_count: int = 0
    branching_factor: float = 0.0
    plan_adherence: float = 0.0
    success: bool = False
    plan_revisions: int = 0
    tool_coverage: float = 0.0

    def to_mapping(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "veto_count": self.veto_count,
            "would_veto_count": self.would_veto_count,
            "branching_factor": round(self.branching_factor, 4),
            "plan_adherence": round(self.plan_adherence, 4),
            "success": self.success,
            "plan_revisions": self.plan_revisions,
            "tool_coverage": round(self.tool_coverage, 4),
        }
        if self.phase_ms:
            payload["phase_ms"] = dict(self.phase_ms)
        return payload

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "InsightMetrics":
        version = str(payload.get("schema_version", cls.schema_version))
        if not is_compatible(version, cls.schema_version):
            raise ValueError(
                f"Incompatible insight schema version '{version}' (expected ≤ {cls.schema_version})"
            )
        phase_source = payload.get("phase_ms")
        if isinstance(phase_source, Mapping):
            phase_ms: Dict[str, Any] = dict(phase_source)
        else:
            phase_ms = {}
        return cls(
            phase_ms=phase_ms,
            veto_count=int(payload.get("veto_count", 0)),
            would_veto_count=int(payload.get("would_veto_count", 0)),
            branching_factor=float(payload.get("branching_factor", 0.0)),
            plan_adherence=float(payload.get("plan_adherence", 0.0)),
            success=bool(payload.get("success", False)),
            plan_revisions=int(payload.get("plan_revisions", 0)),
            tool_coverage=float(payload.get("tool_coverage", 0.0)),
        )


def _first_event_time(events: Iterable[Dict[str, Any]], phase: str) -> Optional[str]:
    for event in events:
        if event.get("phase") == phase:
            return event.get("timestamp")
    return None


def _is_synthetic(event: Mapping[str, Any]) -> bool:
    payload = event.get("payload")
    return isinstance(payload, Mapping) and bool(payload.get("synthetic"))


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
    reflect_success: Optional[bool] = None
    for event in reversed(events):
        phase = event.get("phase")
        if phase == "terminate":
            status = (event.get("payload") or {}).get("status")
            return 1 if status == "ok" else 0
        if reflect_success is None and phase == "reflect":
            payload = event.get("payload") or {}
            value = payload.get("success")
            if isinstance(value, bool):
                reflect_success = value
    if reflect_success is not None:
        return 1 if reflect_success else 0
    return 0


def _is_governance_enforce_veto(payload: Mapping[str, Any]) -> bool:
    if payload.get("decision") != "veto":
        return False
    if payload.get("error"):
        return False
    mode = payload.get("mode")
    enforced = payload.get("enforced")
    if isinstance(mode, str) and mode.lower() == "enforce":
        return bool(enforced) if enforced is not None else True
    return enforced is True


def _is_governance_audit_veto(payload: Mapping[str, Any]) -> bool:
    if payload.get("decision") != "veto":
        return False
    mode = payload.get("mode")
    return isinstance(mode, str) and mode.lower() == "audit"


def compute_metrics(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute roll-up metrics from an episode summary + event stream."""
    direction_events = [event for event in events if event.get("phase") == "direction"]
    governance_events = [event for event in events if event.get("phase") == "governance"]
    plan_events = [
        event
        for event in events
        if event.get("phase") == "plan" and not _is_synthetic(event)
    ]
    reflect_events = [event for event in events if event.get("phase") == "reflect"]
    act_events = [
        event
        for event in events
        if event.get("phase") == "act" and not _is_synthetic(event)
    ]
    interpret_events = [
        event for event in events if event.get("phase") == "interpret"
    ]

    planned_steps = 0
    if plan_events:
        plan_payload = plan_events[-1].get("payload") or {}
        steps_field = plan_payload.get("steps")
        if isinstance(steps_field, Sequence):
            planned_steps = sum(1 for step in steps_field if isinstance(step, str))

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
    governance_vetoed = [
        event
        for event in governance_events
        if _is_governance_enforce_veto(event.get("payload") or {})
    ]
    governance_would_veto = [
        event
        for event in governance_events
        if _is_governance_audit_veto(event.get("payload") or {})
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

    t_veto = _first_event_time(governance_vetoed, "governance")
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
        "governance_vetoed": len(governance_vetoed),
        "governance_would_vetoed": len(governance_would_veto),
        "direction_applied_rate": direction_applied_rate,
        "top_reasons": top_reasons,
        "plan_total": planned_steps,
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


def build_insight_metrics(
    events: Sequence[Dict[str, Any]],
    summary_metrics: Mapping[str, Any] | None = None,
) -> InsightMetrics:
    """Construct InsightMetrics from raw events and aggregate summary data."""
    summary_metrics = summary_metrics or {}
    phase_ms: Dict[str, Optional[int]] = {}
    direction_events = [event for event in events if event.get("phase") == "direction"]
    governance_events = [event for event in events if event.get("phase") == "governance"]
    plan_events = [
        event
        for event in events
        if event.get("phase") == "plan" and not _is_synthetic(event)
    ]
    act_events = [
        event
        for event in events
        if event.get("phase") == "act" and not _is_synthetic(event)
    ]

    for event in events:
        phase = event.get("phase")
        metrics = event.get("metrics") or {}
        duration = metrics.get("duration_ms")
        if phase in {"observe", "interpret", "plan", "act", "reflect"} and duration is not None:
            try:
                duration_val = float(duration)
            except (ValueError, TypeError):
                continue
            if duration_val < 0:
                continue
            phase_ms[phase] = max(1, int(ceil(duration_val)))

    veto_count = sum(
        1
        for event in governance_events
        if _is_governance_enforce_veto(event.get("payload") or {})
    )
    would_veto_count = sum(
        1
        for event in governance_events
        if _is_governance_audit_veto(event.get("payload") or {})
    )
    plan_revisions = sum(
        1
        for event in direction_events
        if (event.get("payload") or {}).get("status") == "applied"
    )
    branching_factor = float(summary_metrics.get("direction_events", len(direction_events)))
    plan_total_value: Optional[float] = None
    summary_plan_total = summary_metrics.get("plan_total")
    if isinstance(summary_plan_total, (int, float)) and summary_plan_total > 0:
        plan_total_value = float(summary_plan_total)
    elif plan_events:
        last_plan_payload = plan_events[-1].get("payload") or {}
        steps_field = last_plan_payload.get("steps")
        if isinstance(steps_field, Sequence):
            plan_total_value = float(
                sum(1 for step in steps_field if isinstance(step, str))
            )
    if plan_total_value is None or plan_total_value <= 0:
        summary_steps = summary_metrics.get("steps")
        if isinstance(summary_steps, (int, float)) and summary_steps > 0:
            plan_total_value = float(summary_steps)
        else:
            plan_total_value = float(len(act_events))

    executed_steps_raw = summary_metrics.get("act_count")
    if isinstance(executed_steps_raw, (int, float)):
        executed_steps = float(executed_steps_raw)
    else:
        executed_steps = float(len(act_events))
    plan_adherence = 0.0
    if plan_total_value > 0:
        plan_adherence = executed_steps / plan_total_value

    success_flag = bool(summary_metrics.get("success", 0))

    tool_labels = set()
    for event in act_events:
        payload = event.get("payload") or {}
        tool = payload.get("tool")
        if tool:
            tool_labels.add(tool)
    tool_coverage = float(len(tool_labels))

    return InsightMetrics(
        phase_ms=phase_ms,
        veto_count=veto_count,
        would_veto_count=would_veto_count,
        branching_factor=branching_factor,
        plan_adherence=plan_adherence,
        success=success_flag,
        plan_revisions=plan_revisions,
        tool_coverage=tool_coverage,
    )


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

    metrics.setdefault("schema_version", InsightMetrics.schema_version)
    metrics.setdefault("phase_ms", {})
    metrics.setdefault("veto_count", metrics.get("governance_vetoed", 0))
    metrics.setdefault("would_veto_count", metrics.get("governance_would_vetoed", 0))
    metrics.setdefault("branching_factor", 0.0)
    metrics.setdefault("plan_adherence", 0.0)
    metrics.setdefault("success", metrics.get("success", 0))

    finalized = InsightMetrics.from_mapping(metrics).to_mapping()
    extras = {key: value for key, value in metrics.items() if key not in finalized}
    finalized.update(extras)
    return finalized
