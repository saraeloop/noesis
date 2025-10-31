"""
Trace schema definitions and versioning for Noēsis.

This module centralizes the schema version constants and lightweight type
hints shared across the tracing pipeline. Keeping them in one place ensures
that runtime, adapters, and documentation stay in lockstep as the schema
evolves.
"""

from __future__ import annotations

from typing import Any, Dict, List, NotRequired, TypedDict

# Public schema version exported to runtime/core.
SUMMARY_SCHEMA_VERSION = "1.1.0"


class EventRecord(TypedDict, total=False):
    """Typed snapshot of a single event emitted to events.jsonl."""

    timestamp: str
    episode_id: str
    agent_id: NotRequired[str]
    phase: str
    payload: Dict[str, Any]
    evidence_ids: List[str]


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


__all__ = [
    "SUMMARY_SCHEMA_VERSION",
    "EventRecord",
    "SummaryFlags",
    "SummarySnapshot",
]
