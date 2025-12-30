from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import sys
import json
from functools import lru_cache

from noesis.trace.events import read_events as read_events_from_dir
from noesis.trace.summary import read_summary as read_summary_from_dir
from noesis.trace.summary import SUMMARY_FILE
from noesis.trace.events import EVENTS_FILE
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION, EVENTS_SCHEMA_VERSION, events_schema_path
from jsonschema import Draft202012Validator
from .viewer_time import parse_iso

SchemaLabel = str


@dataclass
class ValidationIssue:
    file: str
    schema: SchemaLabel
    pointer: str
    message: str
    line: Optional[int] = None

    def format(self) -> str:
        pointer = self.pointer or "$"
        location = self.file
        if self.line is not None:
            location = f"{location}: line {self.line}"
        return f"{location} schema:{self.schema} \u2192 {pointer} {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "file": self.file,
            "schema": self.schema,
            "pointer": self.pointer,
            "message": self.message,
        }
        if self.line is not None:
            data["line"] = self.line
        return data


@dataclass
class TimelineRow:
    timestamp: str
    delta_ms: int
    phase: str
    agent: str
    note: str

    def delta_label(self) -> str:
        seconds = self.delta_ms / 1000
        return f"+{seconds:.3f}s"


@dataclass
class EpisodeView:
    source: str
    episode_id: str
    summary: Dict[str, Any]
    events: List[Dict[str, Any]]
    header: Dict[str, Any]
    kpis: Dict[str, Any]
    governance: Optional[Dict[str, Any]]
    timeline: List[TimelineRow]
    validation: List[ValidationIssue]
    paths: Dict[str, Optional[str]] = field(default_factory=dict)
    schema_version: str = SUMMARY_SCHEMA_VERSION

    @property
    def invalid(self) -> bool:
        return bool(self.validation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "episode_id": self.episode_id,
            "schema_version": self.schema_version,
            "paths": self.paths,
            "summary": self.summary,
            "events": self.events,
            "insights": {
                "header": self.header,
                "kpis": self.kpis,
                "governance": self.governance,
                "timeline": [
                    {
                        "timestamp": row.timestamp,
                        "delta_ms": row.delta_ms,
                        "phase": row.phase,
                        "agent": row.agent,
                        "note": row.note,
                    }
                    for row in self.timeline
                ],
            },
            "validation": [issue.to_dict() for issue in self.validation],
        }


def _first_timestamp(events: Sequence[Dict[str, Any]]) -> Optional[datetime]:
    for event in events:
        ts = event.get("timestamp")
        dt = parse_iso(ts) if isinstance(ts, str) else None
        if dt is not None:
            return dt
    return None


def _note_for_event(phase: str, payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    if phase == "governance":
        decision = payload.get("decision")
        rule = payload.get("rule_id")
        message = payload.get("message")
        parts = [part for part in (decision, rule, message) if part]
        return " · ".join(str(p) for p in parts[:3])
    if phase == "direction":
        status = payload.get("status")
        reason = payload.get("reason")
        steps = payload.get("steps")
        first_step = steps[0] if isinstance(steps, list) and steps else None
        parts = [status, reason, first_step]
        return " · ".join(str(p) for p in parts if p)
    if phase == "plan":
        steps = payload.get("steps")
        if isinstance(steps, list) and steps:
            return str(steps[0])
    if phase == "act":
        outcome = payload.get("outcome")
        tool = payload.get("adapter") or payload.get("tool")
        msg = payload.get("reasons")
        if isinstance(msg, list) and msg:
            msg = msg[0]
        parts = [outcome, tool, msg]
        return " · ".join(str(p) for p in parts if p)
    for key in ("message", "reason", "status", "task", "note"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.splitlines()[0]
    return ""


def _build_timeline(events: List[Dict[str, Any]], base_ts: Optional[datetime] = None) -> List[TimelineRow]:
    timeline: List[TimelineRow] = []
    base = base_ts or _first_timestamp(events)
    for event in events:
        ts = event.get("timestamp", "")
        delta_ms = 0
        event_dt = parse_iso(ts) if isinstance(ts, str) else None
        if base and event_dt:
            try:
                delta_ms = int((event_dt - base).total_seconds() * 1000)
            except Exception:  # noqa: BLE001
                delta_ms = 0
        phase = str(event.get("phase", ""))
        payload = event.get("payload") or {}
        note = _note_for_event(phase, payload)
        agent = event.get("agent_id") or payload.get("agent") or "system"
        timeline.append(TimelineRow(timestamp=ts, delta_ms=delta_ms, phase=phase, agent=str(agent), note=note))
    return timeline


def _policies_from_events(events: Iterable[Dict[str, Any]]) -> List[str]:
    policies: List[str] = []
    seen: set[str] = set()
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        for key in ("policy_id", "policy"):
            value = payload.get(key)
            if isinstance(value, str) and value and value not in seen:
                version = payload.get("policy_version")
                if isinstance(version, str):
                    display = f"{value}@{version}"
                else:
                    display = value
                policies.append(display)
                seen.add(value)
    return policies


def _clamp_phase_ms(metrics: Dict[str, Any]) -> Dict[str, int]:
    phase_ms = metrics.get("phase_ms")
    if not isinstance(phase_ms, dict):
        return {}
    clamped: Dict[str, int] = {}
    for phase, value in phase_ms.items():
        if isinstance(value, (int, float)):
            clamped[phase] = max(1, int(round(value))) if value else 0
    return clamped


def _header(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    flags = summary.get("flags", {}) or {}
    direction_flags = flags.get("direction", {}) or {}
    header = {
        "episode_id": summary.get("episode_id"),
        "started_at": summary.get("started_at"),
        "planner_mode": flags.get("mode"),
        "intuition_enabled": bool(flags.get("intuition")),
        "using": flags.get("using"),
        "policies": _policies_from_events(events) or ([direction_flags.get("policy")] if direction_flags.get("policy") else []),
    }
    ports = summary.get("ports")
    if isinstance(ports, dict):
        header["ports"] = ports
    direction_threshold = direction_flags.get("threshold")
    if direction_threshold is not None:
        header["direction_threshold"] = direction_threshold
    return header


def _kpis(summary: Dict[str, Any]) -> Dict[str, Any]:
    metrics: Dict[str, Any] = summary.get("metrics", {}) or {}
    plan_adherence = metrics.get("plan_adherence")
    veto_count = metrics.get("veto_count")
    tool_coverage = metrics.get("tool_coverage")
    success = metrics.get("success")
    latencies = metrics.get("latencies") or {}
    phase_ms = _clamp_phase_ms(metrics)
    if not phase_ms:
        insight = summary.get("insight", {}) or {}
        insight_metrics = insight.get("metrics", {}) or {}
        phase_ms = _clamp_phase_ms(insight_metrics)
    return {
        "plan_adherence": plan_adherence,
        "veto_count": veto_count,
        "tool_coverage": tool_coverage,
        "success": success,
        "phase_ms": phase_ms,
        "latencies": latencies,
    }


def _governance(summary: Dict[str, Any], events: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for event in reversed(events):
        if event.get("phase") != "governance":
            continue
        payload = event.get("payload") or {}
        latencies = summary.get("metrics", {}).get("latencies", {})
        return {
            "decision": payload.get("decision"),
            "rule_id": payload.get("rule_id"),
            "message": payload.get("message"),
            "score": payload.get("score"),
            "policy_id": payload.get("policy_id"),
            "policy_version": payload.get("policy_version"),
            "time_to_veto_ms": latencies.get("time_to_veto_ms"),
        }
    return None


def _require(condition: bool, *, file: str, schema: str, pointer: str, message: str, line: Optional[int] = None) -> Optional[ValidationIssue]:
    if condition:
        return None
    pointer = pointer if pointer.startswith("$") else f"$.{pointer.lstrip('.')}"
    return ValidationIssue(file=file, schema=schema, pointer=pointer, message=message, line=line)


def validate_summary(summary: Dict[str, Any], *, schema: str, file_label: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    required_fields = ("schema_version", "episode_id", "task", "started_at")
    for field in required_fields:
        issue = _require(field in summary, file=file_label, schema=schema, pointer=field, message="missing")
        if issue:
            issues.append(issue)
    metrics = summary.get("metrics")
    issue = _require(isinstance(metrics, dict), file=file_label, schema=schema, pointer="metrics", message="expected object")
    if issue:
        issues.append(issue)
    else:
        for key in ("plan_adherence", "veto_count", "tool_coverage", "success"):
            issue = _require(key in metrics, file=file_label, schema=schema, pointer=f"metrics.{key}", message="missing")
            if issue:
                issues.append(issue)
        latencies = metrics.get("latencies", {})
        if latencies:
            issue = _require(isinstance(latencies, dict), file=file_label, schema=schema, pointer="metrics.latencies", message="expected object")
            if issue:
                issues.append(issue)
    return issues


def validate_events(
    events: Sequence[Dict[str, Any]],
    *,
    schema: str,
    file_label: str,
    schema_payload: Dict[str, Any],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    validator = Draft202012Validator(schema_payload)
    for index, event in enumerate(events, start=1):
        for error in validator.iter_errors(event):
            issues.append(
                ValidationIssue(
                    file=file_label,
                    schema=schema,
                    pointer=_jsonschema_pointer(error),
                    message=error.message,
                    line=index,
                )
            )
    return issues


def _load_from_run_dir(run_dir: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Optional[str]]]:
    summary = read_summary_from_dir(run_dir)
    events = read_events_from_dir(run_dir)
    paths = {
        "dir": str(run_dir),
        "summary": str(run_dir / SUMMARY_FILE),
        "events": str(run_dir / EVENTS_FILE),
    }
    return summary, events, paths


def _load_from_episode_id(ns: Any, runtime_context: Any, episode_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Optional[str]]]:
    summary = ns.summary.read(episode_id, context=runtime_context)
    events = list(ns.events.read(episode_id, context=runtime_context))
    try:
        paths = ns.io.paths(episode_id, context=runtime_context)
    except Exception:  # noqa: BLE001
        paths = {"dir": None, "summary": None, "events": None}
    return summary, events, paths


def _jsonschema_pointer(error: Exception) -> str:
    path = getattr(error, "absolute_path", ())
    pointer = "$"
    for item in path:
        if isinstance(item, int):
            pointer += f"[{item}]"
        else:
            pointer += f".{item}"
    return pointer


@lru_cache(maxsize=1)
def _events_schema() -> Dict[str, Any]:
    path = Path(events_schema_path())
    return json.loads(path.read_text(encoding="utf-8"))


def load_episode_view(
    target: str,
    *,
    ns: Any,
    runtime_context: Any,
    schema_override: Optional[str] = None,
    debug: bool = False,
) -> EpisodeView:
    candidate = Path(target).expanduser()
    if candidate.exists():
        run_dir = candidate if candidate.is_dir() else candidate.parent
        summary, events, paths = _load_from_run_dir(run_dir)
        source = f"path:{run_dir}"
    else:
        summary, events, paths = _load_from_episode_id(ns, runtime_context, target)
        source = f"episode:{target}"

    schema_version = summary.get("schema_version") or SUMMARY_SCHEMA_VERSION
    if schema_override:
        schema_version = schema_override
    summary_schema_label = f"summary/{schema_version}"
    event_schema_label = f"events/{EVENTS_SCHEMA_VERSION}"

    summary_file_label = Path(paths.get("summary") or "summary.json").name
    events_file_label = Path(paths.get("events") or "events.jsonl").name

    validation: List[ValidationIssue] = []
    events_schema_file = Path(events_schema_path())
    if debug:
        print(f"[debug] events schema: {events_schema_file}", file=sys.stderr)
    validation.extend(validate_summary(summary, schema=summary_schema_label, file_label=summary_file_label))
    validation.extend(
        validate_events(
            events,
            schema=event_schema_label,
            file_label=events_file_label,
            schema_payload=_events_schema(),
        )
    )

    episode_id = summary.get("episode_id") or target
    header = _header(summary, events)
    kpis = _kpis(summary)
    governance = _governance(summary, events)
    timeline = _build_timeline(events)
    return EpisodeView(
        source=source,
        episode_id=episode_id,
        summary=summary,
        events=events,
        header=header,
        kpis=kpis,
        governance=governance,
        timeline=timeline,
        validation=validation,
        paths=paths,
        schema_version=schema_version,
    )
