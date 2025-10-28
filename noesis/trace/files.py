"""
Tracing contracts: events.jsonl (append-only) and summary.json (single file).

Only defines interfaces & helpers; real IO is orchestrated by runner.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Iterator, List, Any
import json
import os
import tempfile

EVENTS_FILE = "events.jsonl"
SUMMARY_FILE = "summary.json"

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


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomic JSON write to prevent partial files on crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)  # POSIX atomic move

    # TODO: add version stamping or hash for traceability


def write_summary(dir_path: Path, summary: Dict[str, Any]) -> None:
    """Write summary.json atomically."""
    _atomic_write_json(dir_path / SUMMARY_FILE, summary)


def read_summary(dir_path: Path) -> Dict[str, Any]:
    """Read summary.json ({} if missing)."""
    p = dir_path / SUMMARY_FILE
    if not p.exists():
        # TODO: log warning if missing during active session
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
