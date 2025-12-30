"""
Trace events: append-only runtime record format for Noēsis.

Purpose
-------
Defines the canonical JSONL schema used to capture execution traces
across all adapters, agents, and intuition layers. Every event is a
single line of structured JSON written to `events.jsonl`, forming an
immutable chronological ledger of the reasoning process.

Design
------
- Append-only by contract — no rewrites, ensuring replay fidelity.
- Human-readable JSON Lines format (1 event per line).
- Phases (`start`, `intuition`, `direction`, `reason`, `observe`,
  `terminate`, `error`, etc.) describe the reasoning lifecycle.
- Schema validation guards consistency without blocking extensions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List, Callable
import json
import warnings

from datetime import datetime
from uuid import uuid4

from noesis.domain.state.cognitive import CognitiveEvent

JsonDefault = Callable[[Any], Any]


def canonical_dumps(value: Any, *, default: JsonDefault | None = None) -> str:
    """
    Render a JSON string with stable ordering and formatting.

    - ensure_ascii=False to preserve UTF-8
    - sort_keys=True for deterministic key order
    - separators=(",", ":") for compact, consistent output
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=default,
    )

EVENTS_FILE = "events.jsonl"
_MANIFEST_FILE = "manifest.json"

# Canonical phases for event.phase
VERB_PHASES: set[str] = {
    "observe",
    "interpret",
    "plan",
    "act",
    "reflect",
    "learn",
}

# Canonical phases for event.phase
PHASES: set[str] = {
    "start",
    "intuition",
    "direction",
    "governance",
    "reason",
    "memory",
    "terminate",
    "error",
    "insight",
    *VERB_PHASES,
}

FACULTY_PHASES: dict[str, str] = {
    "intuition": "intuition",
    "direction": "direction",
    "governance": "governance",
    "insight": "insight",
}

_VERB_PAYLOAD_MINIMA: dict[str, set[str]] = {
    "observe": {"task", "tags", "timestamp"},
    "interpret": {"signals"},
    "plan": {"steps"},
    "act": {"input_excerpt", "outcome"},
    "reflect": {"success"},
}

# Minimal schema contract for events
REQUIRED_EVENT_KEYS: set[str] = {
    "timestamp",
    "episode_id",
    "phase",
    "payload",
    "evidence_ids",
}
RECOMMENDED_EVENT_KEYS: set[str] = {"agent_id"}

__all__ = [
    "EVENTS_FILE",
    "PHASES",
    "REQUIRED_EVENT_KEYS",
    "RECOMMENDED_EVENT_KEYS",
    "is_terminate_event",
    "canonical_dumps",
    "write_event",
    "write_cognitive_event",
    "iter_events",
    "read_events",
    "FACULTY_PHASES",
]


def _validate_event_schema(event: Dict[str, Any]) -> None:
    """Light schema guard for events."""
    missing = REQUIRED_EVENT_KEYS - event.keys()
    if missing:
        raise ValueError(f"event missing required keys: {sorted(missing)}")

    # TODO: enforce stricter phase typing once schemas are frozen
    phase = event.get("phase")
    if isinstance(phase, str) and phase not in PHASES:
        # Allow extensions for now
        pass

    # Basic shape checks
    if not isinstance(event.get("timestamp"), str):
        raise ValueError("event.timestamp must be str (ISO 8601)")
    if not isinstance(event.get("payload"), dict):
        raise ValueError("event.payload must be a dict")
    if not isinstance(event.get("evidence_ids"), list):
        raise ValueError("event.evidence_ids must be a list")
    caused_by = event.get("caused_by")
    if caused_by is not None and not isinstance(caused_by, str):
        raise ValueError("event.caused_by must be a string UUID when provided")
    metrics = event.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError("event.metrics must be a dict when provided")
        for key in ("started_at", "completed_at", "duration_ms"):
            if key not in metrics:
                raise ValueError(f"event.metrics is missing '{key}'")
        if not isinstance(metrics.get("duration_ms"), (int, float)):
            raise ValueError("event.metrics.duration_ms must be numeric")

    if isinstance(phase, str) and phase in VERB_PHASES:
        minima = _VERB_PAYLOAD_MINIMA.get(phase, set())
        payload_keys = set(event["payload"].keys())
        missing_payload = minima - payload_keys
        if missing_payload:
            raise ValueError(
                f"{phase} payload missing required keys: {sorted(missing_payload)}"
            )
        if phase == "act" and not {"tool", "adapter"} & payload_keys:
            raise ValueError("act payload requires either 'tool' or 'adapter'")
        if phase == "learn":
            payload = event["payload"]
            has_ref = any(key in payload for key in ("learn_path", "learn_schema"))
            if has_ref:
                missing = {"learn_path", "learn_schema", "proposal_ids", "proposal_count"} - payload.keys()
                if missing:
                    raise ValueError(
                        f"learn payload missing required keys: {sorted(missing)}"
                    )
                if not isinstance(payload.get("proposal_ids"), list):
                    raise ValueError("learn payload 'proposal_ids' must be a list")
                if not isinstance(payload.get("proposal_count"), int):
                    raise ValueError("learn payload 'proposal_count' must be an int")
                if "applied" in payload and not isinstance(payload.get("applied"), bool):
                    raise ValueError("learn payload 'applied' must be a bool when provided")
                if "applied_count" in payload and not isinstance(payload.get("applied_count"), int):
                    raise ValueError("learn payload 'applied_count' must be an int when provided")
            else:
                missing = {"policy_id", "basis", "proposal", "scope"} - payload.keys()
                if missing:
                    raise ValueError(
                        f"learn payload missing required keys: {sorted(missing)}"
                    )
    faculty = event.get("faculty")
    if faculty is not None and not isinstance(faculty, str):
        raise ValueError("event.faculty must be a string when provided")
    if isinstance(faculty, str) and faculty not in FACULTY_PHASES.values():
        raise ValueError(f"event.faculty must be one of {sorted(set(FACULTY_PHASES.values()))}")


def write_event(dir_path: Path, event: Dict[str, Any], *, validate: bool = True) -> None:
    """Append a single JSON event line (optionally schema-validated)."""
    if "id" not in event:
        event["id"] = str(uuid4())
    _normalize_event_timestamp(event, last_timestamp=_last_event_timestamp(dir_path))
    phase = event.get("phase")
    if isinstance(phase, str) and phase in FACULTY_PHASES and "faculty" not in event:
        event["faculty"] = FACULTY_PHASES[phase]
    if validate:
        _validate_event_schema(event)
    _ensure_manifest_not_sealed(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    payload = canonical_dumps(event)
    with (dir_path / EVENTS_FILE).open("a", encoding="utf-8") as f:
        f.write(payload + "\n")


def write_cognitive_event(
    dir_path: Path,
    event: CognitiveEvent,
    *,
    agent_id: str = "system",
    validate: bool = True,
) -> None:
    """Serialize and append a CognitiveEvent."""
    record = event.to_record()
    record["agent_id"] = agent_id
    write_event(dir_path, record, validate=validate)


def iter_events(dir_path: Path) -> Iterator[Dict[str, Any]]:
    """Yield events from events.jsonl if present."""
    p = dir_path / EVENTS_FILE
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # TODO: surface to logging once logging backend is wired
                # Skip invalid lines rather than failing entire read
                continue


def read_events(dir_path: Path) -> List[Dict[str, Any]]:
    """Return all events ([] if none)."""
    return list(iter_events(dir_path) or ())


def _last_event_timestamp(dir_path: Path) -> str | None:
    path = dir_path / EVENTS_FILE
    if not path.exists():
        return None
    with path.open("rb") as handle:
        handle.seek(0, 2)
        end = handle.tell()
        if end == 0:
            return None
        buffer = bytearray()
        pos = end - 1
        while pos >= 0:
            handle.seek(pos)
            chunk = handle.read(1)
            if chunk == b"\n" and buffer:
                break
            if chunk != b"\n":
                buffer.extend(chunk)
            pos -= 1
        if not buffer:
            return None
        try:
            payload = json.loads(buffer[::-1].decode("utf-8"))
        except json.JSONDecodeError:
            return None
        ts = payload.get("timestamp")
        return ts if isinstance(ts, str) else None


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_event_timestamp(event: Dict[str, Any], *, last_timestamp: str | None) -> str:
    """
    Normalize event timestamps to ensure monotonic ordering.

    Rules:
    - If metrics.completed_at is present, event.timestamp must equal it.
    - Event timestamps must be >= the last emitted timestamp.
    """
    metrics = event.get("metrics")
    has_metrics = isinstance(metrics, dict)
    if has_metrics:
        completed_at = metrics.get("completed_at")
        if isinstance(completed_at, str):
            event["timestamp"] = completed_at
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("event.timestamp must be an ISO 8601 string")

    if last_timestamp:
        current = _parse_iso(timestamp)
        prior = _parse_iso(last_timestamp)
        if current is not None and prior is not None and current < prior:
            if has_metrics:
                raise ValueError(
                    f"event.timestamp {timestamp} is older than prior event timestamp {last_timestamp}"
                )
            event["timestamp"] = last_timestamp
            timestamp = last_timestamp
    return timestamp


def is_terminate_event(event: Dict[str, Any]) -> bool:
    """
    Detect terminate events across schema revisions.

    - Legacy shape: phase == "terminate"
    - Current shape: phase == "runtime" and payload.kind/type/event == "terminate"
    """
    phase = event.get("phase")
    if phase == "terminate":
        return True
    if phase != "runtime":
        return False
    payload = event.get("payload") or {}
    kind = payload.get("kind") or payload.get("type") or payload.get("event")
    return kind == "terminate"


def _ensure_manifest_not_sealed(dir_path: Path) -> None:
    manifest_path = dir_path / _MANIFEST_FILE
    if manifest_path.exists():
        warnings.warn(
            f"Manifest {manifest_path} already exists; refusing to append events.",
            RuntimeWarning,
            stacklevel=3,
        )
        raise RuntimeError("cannot append events after manifest is finalized")
