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
    "reason",
    "memory",
    "terminate",
    "error",
    "insight",
    *VERB_PHASES,
}

_VERB_PAYLOAD_MINIMA: dict[str, set[str]] = {
    "observe": {"task", "tags", "timestamp"},
    "interpret": {"signals"},
    "plan": {"steps"},
    "act": {"input_excerpt", "outcome"},
    "reflect": {"success"},
    "learn": {"policy_id", "basis", "proposal", "applied", "scope"},
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
    "canonical_dumps",
    "write_event",
    "write_cognitive_event",
    "iter_events",
    "read_events",
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
            if not isinstance(payload.get("proposal"), list):
                raise ValueError("learn payload 'proposal' must be a list")


def write_event(dir_path: Path, event: Dict[str, Any], *, validate: bool = True) -> None:
    """Append a single JSON event line (optionally schema-validated)."""
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


def _ensure_manifest_not_sealed(dir_path: Path) -> None:
    manifest_path = dir_path / _MANIFEST_FILE
    if manifest_path.exists():
        warnings.warn(
            f"Manifest {manifest_path} already exists; refusing to append events.",
            RuntimeWarning,
            stacklevel=3,
        )
        raise RuntimeError("cannot append events after manifest is finalized")
