"""
Intuition contracts: lightweight advisory layer emitting directional hints.

JSON-friendly by design; model- and framework-agnostic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, TypeAlias

# Public surface
__all__ = ["IntuitionEvent", "Intuition", "NullIntuition", "StateSnapshot"]

# TODO: consider Literal types for 'kind' once policy enums stabilize
StateSnapshot: TypeAlias = Dict[str, Any]


@dataclass(slots=True)
class IntuitionEvent:
    """Structured record of an intuition signal."""
    kind: str                     # e.g., "forecast", "risk", "routing", "budget"
    advice: str                   # human-readable, actionable hint
    confidence: float             # [0.0, 1.0]
    applied: bool = False         # whether the system acted on this advice
    rationale: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Clamp to a sane range; avoid downstream math errors.
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0


class Intuition(Protocol):
    """Interface for intuition policies (pure advisory)."""

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        """
        Analyze the current reasoning context and optionally emit a hint.

        Parameters
        ----------
        state : StateSnapshot
            Snapshot of task, history, tools_seen, tags, etc.

        Returns
        -------
        Optional[IntuitionEvent]
            Directional hint or None if no advice is triggered.
        """
        ...


class NullIntuition:
    """Baseline intuition: no-op policy used when intuition is OFF."""
    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        # Intentional no-op; keeps call sites uniform.
        return None