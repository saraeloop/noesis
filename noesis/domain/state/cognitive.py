"""
Domain primitives for the Noēsis cognitive loop.

These value objects formalize the six cognitive verbs and the structure of
runtime events so that upstream layers can reason about lineage and timing
without depending on infrastructure code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence
from uuid import UUID, uuid4

__all__ = [
    "CognitiveVerb",
    "COGNITIVE_VERBS",
    "CognitiveMetrics",
    "CognitiveEvent",
    "LineageTracker",
]


class CognitiveVerb(str, Enum):
    """Canonical cognitive verbs emitted by the runtime."""

    OBSERVE = "observe"
    INTERPRET = "interpret"
    PLAN = "plan"
    ACT = "act"
    REFLECT = "reflect"
    LEARN = "learn"


COGNITIVE_VERBS: tuple[CognitiveVerb, ...] = tuple(CognitiveVerb)


def _ensure_dict(payload: Mapping[str, object]) -> Dict[str, object]:
    return dict(payload) if not isinstance(payload, dict) else payload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CognitiveMetrics:
    """Timing metadata captured for a cognitive verb execution."""

    started_at: datetime
    completed_at: datetime
    duration_ms: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass(frozen=True, slots=True)
class CognitiveEvent:
    """Immutable representation of a cognitive verb emission."""

    episode_id: str
    verb: CognitiveVerb
    payload: Mapping[str, object]
    evidence_ids: Sequence[str] = ()
    timestamp: datetime = field(default_factory=_utcnow)
    event_id: UUID = field(default_factory=uuid4)
    caused_by: Optional[UUID] = None
    metrics: Optional[CognitiveMetrics] = None

    def with_metrics(self, metrics: CognitiveMetrics) -> "CognitiveEvent":
        return replace(self, metrics=metrics)

    def with_cause(self, caused_by: Optional[UUID]) -> "CognitiveEvent":
        return replace(self, caused_by=caused_by)

    def to_record(self) -> Dict[str, object]:
        """Render the event into the JSON-serializable schema used by trace writers."""
        record: Dict[str, object] = {
            "id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "episode_id": self.episode_id,
            "phase": self.verb.value,
            "payload": _ensure_dict(self.payload),
            "evidence_ids": list(self.evidence_ids),
        }
        if self.caused_by:
            record["caused_by"] = str(self.caused_by)
        if self.metrics:
            record["metrics"] = self.metrics.to_dict()
        return record


class LineageTracker:
    """
    Runtime helper that enforces causal links and reports coverage.

    The tracker is intentionally side-effect free: it only returns enriched copies
    of events so it can live safely in the domain layer.
    """

    __slots__ = ("_last_event_id", "_registrations", "_linked")

    def __init__(self) -> None:
        self._last_event_id: Optional[UUID] = None
        self._registrations = 0
        self._linked = 0

    def register(self, event: CognitiveEvent, *, cause: Optional[UUID] = None) -> CognitiveEvent:
        self._registrations += 1
        causal_source = event.caused_by or cause or self._last_event_id
        linked_event = event if causal_source is None else event.with_cause(causal_source)
        if linked_event.caused_by:
            self._linked += 1
        self._last_event_id = linked_event.event_id
        return linked_event

    @property
    def last_event_id(self) -> Optional[UUID]:
        return self._last_event_id

    def coverage(self) -> float:
        if self._registrations == 0:
            return 0.0
        return round(self._linked / self._registrations, 4)

    def snapshot(self) -> Dict[str, object]:
        return {
            "registrations": self._registrations,
            "linked": self._linked,
            "coverage": self.coverage(),
        }

    def seed(self, *, last_event_id: Optional[UUID]) -> None:
        """Initialize lineage with a pre-existing event ID without counting coverage."""
        self._last_event_id = last_event_id
