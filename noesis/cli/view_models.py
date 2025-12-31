from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import json

from jsonschema import Draft202012Validator

from noesis.cli import formatters
from noesis.cli.viewer_time import parse_iso
from noesis.trace.schema import EVENTS_SCHEMA_VERSION, SUMMARY_SCHEMA_VERSION, events_schema_path
from noesis.trace.events import EVENTS_FILE
from noesis.trace.summary import SUMMARY_FILE

from .query import (
    duration_seconds,
    episode_status,
    iter_events,
    phase_latencies_ms,
    read_manifest,
    read_state,
    read_summary,
    schema_label,
    status_label,
)


@dataclass(frozen=True)
class EpisodeHeaderVM:
    episode_id: str
    status_label: str
    started_at: Optional[str]
    duration: Optional[float]


@dataclass(frozen=True)
class EpisodeChipsVM:
    using: Optional[str]
    planner_mode: Optional[str]
    duration_str: Optional[str]
    schema_str: Optional[str]


@dataclass(frozen=True)
class EpisodeKpisVM:
    success_pct: Optional[float]
    plan_adherence: Optional[float]
    veto_count: Optional[int]
    tool_coverage: Optional[float]
    first_action: Optional[str]


@dataclass(frozen=True)
class PhaseLatencyVM:
    phase: str
    ms: int


@dataclass(frozen=True)
class TimelineRowVM:
    dt_str: str
    phase: str
    agent: str
    status: str
    summary: str


@dataclass(frozen=True)
class EpisodeDashboardVM:
    header: EpisodeHeaderVM
    chips: EpisodeChipsVM
    kpis: EpisodeKpisVM
    phase_breakdown: List[PhaseLatencyVM]
    timeline_rows: List[TimelineRowVM]
    validation_issues: List[str]
    suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": {
                "episode_id": self.header.episode_id,
                "status_label": self.header.status_label,
                "started_at": self.header.started_at,
                "duration": self.header.duration,
            },
            "chips": {
                "using": self.chips.using,
                "planner_mode": self.chips.planner_mode,
                "duration_str": self.chips.duration_str,
                "schema_str": self.chips.schema_str,
            },
            "kpis": {
                "success_pct": self.kpis.success_pct,
                "plan_adherence": self.kpis.plan_adherence,
                "veto_count": self.kpis.veto_count,
                "tool_coverage": self.kpis.tool_coverage,
                "first_action": self.kpis.first_action,
            },
            "phase_breakdown": [
                {"phase": item.phase, "ms": item.ms} for item in self.phase_breakdown
            ],
            "timeline_rows": [
                {
                    "dt_str": row.dt_str,
                    "phase": row.phase,
                    "agent": row.agent,
                    "status": row.status,
                    "summary": row.summary,
                }
                for row in self.timeline_rows
            ],
            "validation_issues": list(self.validation_issues),
            "suggestions": list(self.suggestions),
        }


def build_episode_dashboard(
    ep_dir: Path,
    *,
    limit_timeline: int = 50,
    validate: bool = False,
    schema_override: Optional[str] = None,
) -> EpisodeDashboardVM:
    summary = read_summary(ep_dir) or {}
    state = read_state(ep_dir) or {}
    events = list(iter_events(ep_dir))
    _ = read_manifest(ep_dir)

    episode_id = summary.get("episode_id") if isinstance(summary, dict) else None
    if not episode_id:
        episode_id = ep_dir.name

    status = episode_status(summary, state, events)
    flags = summary.get("flags", {}) if isinstance(summary, dict) else {}
    status_text = status_label(status, governance_mode=flags.get("governance_mode"))
    started_at = summary.get("started_at") if isinstance(summary, dict) else None
    duration = duration_seconds(summary, events)
    duration_str = formatters.format_duration(duration)

    chips = EpisodeChipsVM(
        using=flags.get("using"),
        planner_mode=flags.get("mode"),
        duration_str=duration_str,
        schema_str=schema_label(summary),
    )

    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    success_pct = _success_pct(metrics.get("success"))
    kpis = EpisodeKpisVM(
        success_pct=success_pct,
        plan_adherence=_coerce_float(metrics.get("plan_adherence")),
        veto_count=_coerce_int(metrics.get("veto_count")),
        tool_coverage=_coerce_float(metrics.get("tool_coverage")),
        first_action=_first_action(events),
    )

    phase_breakdown = _phase_breakdown(summary, events)
    timeline_rows = _build_timeline(events, limit_timeline=limit_timeline)
    validation_issues = _validate_artifacts(
        ep_dir,
        summary=summary,
        events=events,
        validate=validate,
        schema_override=schema_override,
    )
    suggestions = _suggestions(episode_id)

    return EpisodeDashboardVM(
        header=EpisodeHeaderVM(
            episode_id=episode_id,
            status_label=status_text,
            started_at=started_at,
            duration=duration,
        ),
        chips=chips,
        kpis=kpis,
        phase_breakdown=phase_breakdown,
        timeline_rows=timeline_rows,
        validation_issues=validation_issues,
        suggestions=suggestions,
    )


def build_episode_dashboard_from_payloads(
    *,
    summary: Dict[str, Any] | None,
    events: Sequence[Dict[str, Any]] | None,
    state: Dict[str, Any] | None = None,
    episode_id: Optional[str] = None,
    limit_timeline: int = 50,
    validate: bool = False,
    schema_override: Optional[str] = None,
) -> EpisodeDashboardVM:
    """Build a dashboard view model from in-memory summary/events payloads."""
    summary_payload = summary if isinstance(summary, dict) else {}
    events_payload = list(events or [])

    resolved_id = (
        summary_payload.get("episode_id")
        or _episode_id_from_events(events_payload)
        or episode_id
        or "unknown"
    )

    status = episode_status(summary_payload, state, events_payload)
    flags = summary_payload.get("flags", {}) if isinstance(summary_payload, dict) else {}
    status_text = status_label(status, governance_mode=flags.get("governance_mode"))
    started_at = summary_payload.get("started_at") if isinstance(summary_payload, dict) else None
    duration = duration_seconds(summary_payload, events_payload)
    duration_str = formatters.format_duration(duration)

    chips = EpisodeChipsVM(
        using=flags.get("using"),
        planner_mode=flags.get("mode"),
        duration_str=duration_str,
        schema_str=schema_label(summary_payload),
    )

    metrics = summary_payload.get("metrics", {}) if isinstance(summary_payload, dict) else {}
    success_pct = _success_pct(metrics.get("success"))
    kpis = EpisodeKpisVM(
        success_pct=success_pct,
        plan_adherence=_coerce_float(metrics.get("plan_adherence")),
        veto_count=_coerce_int(metrics.get("veto_count")),
        tool_coverage=_coerce_float(metrics.get("tool_coverage")),
        first_action=_first_action(events_payload),
    )

    phase_breakdown = _phase_breakdown(summary_payload, events_payload)
    timeline_rows = _build_timeline(events_payload, limit_timeline=limit_timeline)
    validation_issues = _validate_payloads(
        summary_payload,
        events_payload,
        validate=validate,
        schema_override=schema_override,
    )
    suggestions = _suggestions(resolved_id)

    return EpisodeDashboardVM(
        header=EpisodeHeaderVM(
            episode_id=resolved_id,
            status_label=status_text,
            started_at=started_at,
            duration=duration,
        ),
        chips=chips,
        kpis=kpis,
        phase_breakdown=phase_breakdown,
        timeline_rows=timeline_rows,
        validation_issues=validation_issues,
        suggestions=suggestions,
    )


def _phase_breakdown(summary: Dict[str, Any], events: Sequence[Dict[str, Any]]) -> List[PhaseLatencyVM]:
    phase_ms = phase_latencies_ms(summary, events)
    items = [
        PhaseLatencyVM(phase=str(phase), ms=int(ms))
        for phase, ms in phase_ms.items()
        if isinstance(phase, str)
    ]
    items.sort(key=lambda item: item.phase)
    return items


def _episode_id_from_events(events: Sequence[Dict[str, Any]]) -> Optional[str]:
    for event in events:
        episode_id = event.get("episode_id")
        if isinstance(episode_id, str) and episode_id:
            return episode_id
    return None


def _build_timeline(events: Sequence[Dict[str, Any]], *, limit_timeline: int) -> List[TimelineRowVM]:
    ordered = _sorted_events(events)
    base_ts = _first_timestamp(ordered)
    rows: List[TimelineRowVM] = []
    for event in ordered:
        delta_str = _delta_str(base_ts, event.get("timestamp"))
        phase = str(event.get("phase") or "")
        payload = event.get("payload") or {}
        agent = event.get("agent_id") or payload.get("agent") or "system"
        status = _status_for_event(payload)
        summary = _summary_for_event(phase, payload)
        rows.append(
            TimelineRowVM(
                dt_str=delta_str,
                phase=phase,
                agent=str(agent),
                status=status,
                summary=summary,
            )
        )
    if limit_timeline and len(rows) > limit_timeline:
        rows = rows[-limit_timeline:]
    return rows


def _sorted_events(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed: List[tuple[int, Optional[str], Dict[str, Any]]] = []
    for idx, event in enumerate(events):
        timestamp = event.get("timestamp")
        indexed.append((idx, timestamp if isinstance(timestamp, str) else None, event))

    def _key(item: tuple[int, Optional[str], Dict[str, Any]]):
        idx, timestamp, _ = item
        dt = parse_iso(timestamp) if timestamp else None
        order = dt.timestamp() if dt is not None else float("inf")
        return (order, idx)

    indexed.sort(key=_key)
    return [item[2] for item in indexed]


def _first_timestamp(events: Sequence[Dict[str, Any]]) -> Optional[str]:
    for event in events:
        ts = event.get("timestamp")
        if isinstance(ts, str):
            return ts
    return None


def _delta_str(base_ts: Optional[str], event_ts: Any) -> str:
    base_dt = parse_iso(base_ts) if isinstance(base_ts, str) else None
    event_dt = parse_iso(event_ts) if isinstance(event_ts, str) else None
    if base_dt and event_dt:
        delta_s = max(0.0, (event_dt - base_dt).total_seconds())
        return f"+{delta_s:.3f}s"
    return "+0.000s"


def _summary_for_event(phase: str, payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    message = payload.get("message")
    if isinstance(message, str) and message:
        return formatters.truncate(message.splitlines()[0], max_width=60)
    task = payload.get("task")
    if isinstance(task, str) and task:
        return formatters.truncate(task.splitlines()[0], max_width=60)
    steps = payload.get("steps")
    if isinstance(steps, list) and steps:
        first = steps[0]
        if isinstance(first, dict):
            desc = first.get("description") or first.get("title")
            if isinstance(desc, str) and desc:
                return formatters.truncate(desc.splitlines()[0], max_width=60)
        if isinstance(first, str):
            return formatters.truncate(first.splitlines()[0], max_width=60)
    adapter = payload.get("adapter") or payload.get("tool")
    outcome = payload.get("outcome")
    if adapter or outcome:
        if adapter and outcome:
            return formatters.truncate(f"{adapter}: {outcome}", max_width=60)
        return formatters.truncate(str(adapter or outcome), max_width=60)
    if phase == "governance":
        gov_message = payload.get("message") or payload.get("decision")
        if isinstance(gov_message, str) and gov_message:
            return formatters.truncate(gov_message.splitlines()[0], max_width=60)
    if phase == "terminate":
        term_message = payload.get("message") or payload.get("status")
        if isinstance(term_message, str) and term_message:
            return formatters.truncate(term_message.splitlines()[0], max_width=60)
    for key in ("status", "reason", "note"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return formatters.truncate(value.splitlines()[0], max_width=60)
    return ""


def _status_for_event(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("status", "decision", "outcome"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _first_action(events: Sequence[Dict[str, Any]]) -> Optional[str]:
    for event in _sorted_events(events):
        if event.get("phase") != "act":
            continue
        payload = event.get("payload") or {}
        for key in ("tool", "adapter", "input_excerpt", "outcome"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return formatters.truncate(value.splitlines()[0], max_width=40)
    return None


def _suggestions(episode_id: str) -> List[str]:
    return [
        f"noesis events {episode_id}",
        f"noesis show {episode_id}",
        f"noesis artifacts verify {episode_id}",
    ]


def _success_pct(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        numeric = float(value)
        if 0.0 <= numeric <= 1.0:
            return round(numeric * 100.0, 2)
        return round(numeric, 2)
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _validate_artifacts(
    ep_dir: Path,
    *,
    summary: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    validate: bool,
    schema_override: Optional[str],
) -> List[str]:
    if not validate:
        return []
    issues: List[str] = []
    summary_path = ep_dir / SUMMARY_FILE
    if not summary_path.exists():
        issues.append("summary.json missing")
        return issues
    events_path = ep_dir / EVENTS_FILE
    if not events_path.exists():
        issues.append("events.jsonl missing")
        return issues

    summary_version = summary.get("schema_version") or SUMMARY_SCHEMA_VERSION
    if schema_override:
        summary_version = schema_override
    summary_label = f"summary/{summary_version}"
    for field in ("schema_version", "episode_id", "started_at", "metrics"):
        if field not in summary:
            issues.append(_format_issue(summary_path.name, summary_label, f"$.{field}", "missing"))
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        issues.append(_format_issue(summary_path.name, summary_label, "$.metrics", "expected object"))
    else:
        for key in ("plan_adherence", "veto_count", "tool_coverage", "success"):
            if key not in metrics:
                issues.append(_format_issue(summary_path.name, summary_label, f"$.metrics.{key}", "missing"))

    issues.extend(_validate_events(events, events_path.name))
    return issues


def _validate_payloads(
    summary: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    *,
    validate: bool,
    schema_override: Optional[str],
) -> List[str]:
    if not validate:
        return []

    issues: List[str] = []
    summary_version = summary.get("schema_version") or SUMMARY_SCHEMA_VERSION
    if schema_override:
        summary_version = schema_override
    summary_label = f"summary/{summary_version}"

    for field in ("schema_version", "episode_id", "started_at", "metrics"):
        if field not in summary:
            issues.append(_format_issue("summary.json", summary_label, f"$.{field}", "missing"))

    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        issues.append(_format_issue("summary.json", summary_label, "$.metrics", "expected object"))
    else:
        for key in ("plan_adherence", "veto_count", "tool_coverage", "success"):
            if key not in metrics:
                issues.append(_format_issue("summary.json", summary_label, f"$.metrics.{key}", "missing"))

    issues.extend(_validate_events(events, "events.jsonl"))
    return issues


def _format_issue(file_label: str, schema_label: str, pointer: str, message: str, line: Optional[int] = None) -> str:
    location = file_label
    if line is not None:
        location = f"{location}: line {line}"
    return f"{location} schema:{schema_label} -> {pointer} {message}"


@lru_cache(maxsize=1)
def _events_schema() -> Dict[str, Any]:
    path = Path(events_schema_path())
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_events(events: Iterable[Dict[str, Any]], file_label: str) -> List[str]:
    issues: List[str] = []
    schema_label = f"events/{EVENTS_SCHEMA_VERSION}"
    validator = Draft202012Validator(_events_schema())
    for index, event in enumerate(events, start=1):
        for error in validator.iter_errors(event):
            pointer = _jsonschema_pointer(error)
            issues.append(_format_issue(file_label, schema_label, pointer, error.message, line=index))
    return issues


def _jsonschema_pointer(error: Exception) -> str:
    path = getattr(error, "absolute_path", ())
    pointer = "$"
    for item in path:
        if isinstance(item, int):
            pointer += f"[{item}]"
        else:
            pointer += f".{item}"
    return pointer
