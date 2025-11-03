"""
Trace schema definitions and versioning for Noēsis.

This module centralizes the schema version constants and lightweight type
hints shared across the tracing pipeline. Keeping them in one place ensures
that runtime, adapters, and documentation stay in lockstep as the schema
evolves.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any, Dict, List, NotRequired, TypedDict

# Public schema version exported to runtime/core.
SUMMARY_SCHEMA_VERSION = "1.2.0"

_FACULTY_SCHEMA_FILES: Dict[str, str] = {
    "intuition": "intuition.schema.json",
    "direction": "direction.schema.json",
    "governance": "governance.schema.json",
    "insight": "insight.schema.json",
}


class EventMetrics(TypedDict):
    """Timing metadata emitted for cognitive verbs."""

    started_at: str
    completed_at: str
    duration_ms: float


class EventRecord(TypedDict, total=False):
    """Typed snapshot of a single event emitted to events.jsonl."""

    id: str
    timestamp: str
    episode_id: str
    agent_id: NotRequired[str]
    phase: str
    payload: Dict[str, Any]
    evidence_ids: List[str]
    caused_by: NotRequired[str]
    metrics: NotRequired[EventMetrics]


class SummaryFlags(TypedDict, total=False):
    """Flags nested under summary['flags']."""

    intuition: bool
    mode: str
    using: NotRequired[str]
    direction: NotRequired[Dict[str, Any]]


class SummarySnapshot(TypedDict, total=False):
    """Typed representation of summary.json content."""

    schema_version: str
    episode_id: str
    task: str
    seed: int
    started_at: str
    duration_sec: float
    flags: SummaryFlags
    agents_config_hash: str
    answer: Dict[str, Any]
    metrics: Dict[str, Any]
    tags: Dict[str, Any]


def schema_path(name: str) -> str:
    """Return the filesystem path for a faculty JSON schema."""
    normalized = name.lower()
    try:
        filename = _FACULTY_SCHEMA_FILES[normalized]
    except KeyError as err:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown faculty schema '{name}'") from err
    return str(files("noesis.trace.schemas") / filename)


__all__ = [
    "SUMMARY_SCHEMA_VERSION",
    "EventRecord",
    "SummaryFlags",
    "SummarySnapshot",
    "EventMetrics",
    "schema_path",
]
