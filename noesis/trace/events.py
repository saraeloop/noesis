"""
Trace event helpers.

Defines the append-only JSONL contract used to capture runtime events.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List
import json

EVENTS_FILE = "events.jsonl"

# Canonical phases for event.phase
PHASES: set[str] = {
    "start",
    "intuition",
    "direction",
    "reason",
    "act",
    "memory",
    "terminate",
    "error",
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
