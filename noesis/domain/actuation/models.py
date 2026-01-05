"""
Internal actuation models.

These types describe execution outcomes without binding to adapters or runtime
infrastructure. They are intentionally internal and not part of the public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class ActuationStatus(str, Enum):
    """Execution outcome for governed actuation."""

    OK = "ok"
    ERROR = "error"
    BLOCKED = "blocked"
    ABORTED = "aborted"


@dataclass(slots=True)
class ActuationResult:
    """Structured outcome for actuation workflows."""

    status: ActuationStatus
    summary: str | None = None
    error: Mapping[str, object] | None = None
    artifacts: Sequence[Mapping[str, object]] = ()
    duration_ms: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    metrics: Mapping[str, float] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, object]:
        payload: dict[str, object] = {"status": self.status.value}
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.error:
            payload["error"] = dict(self.error)
        if self.artifacts:
            payload["artifacts"] = list(self.artifacts)
        if self.duration_ms is not None:
            payload["duration_ms"] = int(self.duration_ms)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.reasons:
            payload["reasons"] = list(self.reasons)
        if self.metrics:
            payload["metrics"] = dict(self.metrics)
        return payload


__all__ = ["ActuationResult", "ActuationStatus"]
