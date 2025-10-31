"""Core intuition abstractions for Noēsis policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, TypeAlias

__all__ = [
    "IntuitionMode",
    "StateSnapshot",
    "IntuitionEvent",
    "Intuition",
    "NullIntuition",
]


class IntuitionMode(str, Enum):
    """Execution posture for an intuition policy."""

    ADVISORY = "advisory"
    INTERVENTIVE = "interventive"
    HYBRID = "hybrid"


StateSnapshot: TypeAlias = Dict[str, Any]


@dataclass(slots=True)
class IntuitionEvent:
    kind: str
    advice: str
    confidence: float
    applied: bool = False
    rationale: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    patch: Optional[Dict[str, Any]] = None
    target: str = "input"
    scope: str = "episode"
    blocking: bool = False

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        try:
            from noesis.domain.faculties.direction import DirectiveKind  # avoid cycle
        except Exception:
            DirectiveKind = None  # type: ignore[assignment]

        if DirectiveKind is not None:
            try:
                DirectiveKind(self.kind)
            except ValueError:
                if self.blocking:
                    self.kind = DirectiveKind.VETO.value


class Intuition(Protocol):
    mode: IntuitionMode

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        ...


class NullIntuition:
    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        return None
