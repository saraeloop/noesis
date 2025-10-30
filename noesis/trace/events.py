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
from typing import Any, Dict, Iterator, List
import json

EVENTS_FILE = "events.jsonl"

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
    "learn": {"updates", "scope"},
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
    "write_event",
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


def write_event(dir_path: Path, event: Dict[str, Any], *, validate: bool = True) -> None:
    """Append a single JSON event line (optionally schema-validated)."""
    if validate:
        _validate_event_schema(event)
    dir_path.mkdir(parents=True, exist_ok=True)
    with (dir_path / EVENTS_FILE).open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


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
