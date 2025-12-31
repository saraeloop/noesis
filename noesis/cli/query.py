from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Sequence
import json

from noesis.trace.events import EVENTS_FILE, iter_events as _iter_events
from noesis.trace.summary import SUMMARY_FILE, read_summary as _read_summary
from noesis.trace.schema import EVENTS_SCHEMA_VERSION, SUMMARY_SCHEMA_VERSION
from noesis.cli.viewer_time import parse_iso
from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME

STATE_FILE = "state.json"


def load_episode_dir(episode_id: str, runs_dir: Path) -> Path:
    return runs_dir.expanduser() / episode_id


def read_summary(ep_dir: Path) -> Optional[Dict[str, Any]]:
    path = ep_dir / SUMMARY_FILE
    if not path.exists():
        return None
    summary = _read_summary(ep_dir)
    return summary or None


def read_state(ep_dir: Path) -> Optional[Dict[str, Any]]:
    path = ep_dir / STATE_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def iter_events(ep_dir: Path) -> Iterator[Dict[str, Any]]:
    return _iter_events(ep_dir) or iter(())


def read_manifest(ep_dir: Path) -> Optional[Dict[str, Any]]:
    path = ep_dir / MANIFEST_FILE_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def episode_status(
    summary: Optional[Dict[str, Any]],
    state: Optional[Dict[str, Any]],
    events: Optional[Sequence[Dict[str, Any]]],
) -> str:
    for source in (summary, state):
        if isinstance(source, dict):
            status = source.get("status")
            if isinstance(status, str) and status:
                return status.lower()

    if events:
        for event in reversed(events):
            phase = event.get("phase")
            payload = event.get("payload") or {}
            if phase == "error":
                return "error"
            if phase == "terminate":
                status = payload.get("status")
                if isinstance(status, str) and status:
                    return status.lower()

    metrics = (summary or {}).get("metrics", {}) if isinstance(summary, dict) else {}
    flags = (summary or {}).get("flags", {}) if isinstance(summary, dict) else {}
    governance_mode = flags.get("governance_mode")
    veto_count = metrics.get("veto_count")
    success = metrics.get("success")
    if isinstance(veto_count, int) and veto_count > 0 and governance_mode == "enforce":
        return "vetoed"
    if success in {0, False}:
        return "error"
    return "ok"


def status_label(status: str, *, governance_mode: Optional[str] = None) -> str:
    normalized = status.lower()
    if normalized == "vetoed":
        return "VETOED"
    if normalized == "error":
        return "ERROR"
    if normalized == "ok":
        if governance_mode == "audit":
            return "AUDIT"
        return "SUCCESS"
    return normalized.upper()


def duration_seconds(
    summary: Optional[Dict[str, Any]],
    events: Optional[Sequence[Dict[str, Any]]],
) -> Optional[float]:
    if isinstance(summary, dict):
        duration = summary.get("duration_sec")
        if isinstance(duration, (int, float)):
            return float(duration)

    if not events:
        return None
    timestamps = []
    for event in events:
        ts = event.get("timestamp")
        dt = parse_iso(ts) if isinstance(ts, str) else None
        if dt is not None:
            timestamps.append(dt)
    if len(timestamps) >= 2:
        delta = (max(timestamps) - min(timestamps)).total_seconds()
        return max(0.0, float(delta))
    return None


def phase_latencies_ms(
    summary: Optional[Dict[str, Any]],
    events: Optional[Sequence[Dict[str, Any]]],
) -> Dict[str, int]:
    insight = (summary or {}).get("insight", {}) if isinstance(summary, dict) else {}
    insight_metrics = insight.get("metrics", {}) if isinstance(insight, dict) else {}
    phase_ms = insight_metrics.get("phase_ms")
    if isinstance(phase_ms, dict):
        return {phase: int(round(value)) for phase, value in phase_ms.items() if isinstance(value, (int, float))}

    totals: Dict[str, float] = {}
    for event in events or []:
        metrics = event.get("metrics") or {}
        duration = metrics.get("duration_ms")
        if not isinstance(duration, (int, float)):
            continue
        phase = event.get("phase")
        if not isinstance(phase, str) or not phase:
            continue
        totals[phase] = totals.get(phase, 0.0) + float(duration)
    return {phase: int(round(value)) for phase, value in totals.items()}


def schema_label(summary: Optional[Dict[str, Any]]) -> str:
    summary_version = SUMMARY_SCHEMA_VERSION
    if isinstance(summary, dict):
        candidate = summary.get("schema_version")
        if isinstance(candidate, str) and candidate:
            summary_version = candidate
    return f"s/{summary_version} e/{EVENTS_SCHEMA_VERSION}"
