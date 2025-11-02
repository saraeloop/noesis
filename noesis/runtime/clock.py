"""
Runtime clock instrumentation for cognitive phases.

The clock lives in the runtime layer because it depends on wall-clock time
and therefore should not be part of the pure domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter_ns
from typing import Optional

from noesis.domain.state.cognitive import CognitiveMetrics, CognitiveVerb

__all__ = ["RuntimeClock", "PhaseToken"]


@dataclass(slots=True)
class PhaseToken:
    """Opaque handle returned when a phase starts."""

    verb: CognitiveVerb
    started_at: datetime
    start_ns: int


class RuntimeClock:
    """High-resolution timer for measuring cognitive verb durations."""

    __slots__ = ("_last_metrics",)

    def __init__(self) -> None:
        self._last_metrics: dict[CognitiveVerb, CognitiveMetrics] = {}

    def start(self, verb: CognitiveVerb) -> PhaseToken:
        return PhaseToken(
            verb=verb,
            started_at=datetime.now(timezone.utc),
            start_ns=perf_counter_ns(),
        )

    def stop(self, token: PhaseToken) -> CognitiveMetrics:
        completed_at = datetime.now(timezone.utc)
        duration_ms = (perf_counter_ns() - token.start_ns) / 1_000_000
        metrics = CognitiveMetrics(
            started_at=token.started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
        self._last_metrics[token.verb] = metrics
        return metrics

    def last_metrics(self, verb: CognitiveVerb) -> Optional[CognitiveMetrics]:
        return self._last_metrics.get(verb)
