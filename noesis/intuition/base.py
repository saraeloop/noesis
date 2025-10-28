"""
Intuition Contracts — the advisory layer of Noēsis.

Defines a minimal, JSON-friendly structure for reasoning hints and
lightweight heuristic feedback during execution.

Key design goals:
- Framework-agnostic and model-agnostic.
- Research-friendly: introspectable, loggable, replayable.
- Cleanly typed: no dependencies beyond the stdlib.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, TypeAlias
from .mode import IntuitionMode

__all__ = [
    "IntuitionEvent",
    "Intuition",
    "NullIntuition",
    "StateSnapshot",
    "DirectiveKind",
    "DirectedIntuition",
]

# A reasoning snapshot handed to intuition policies
StateSnapshot: TypeAlias = Dict[str, Any]


# Event structure

class DirectiveKind(str, Enum):
    """Direction families emitted by intuition policies."""

    HINT = "hint"
    INTERVENTION = "intervention"
    VETO = "veto"


@dataclass(slots=True)
class IntuitionEvent:
    """
    A structured record of an intuition signal.

    Parameters
    ----------
    kind : str
        Category of intuition (e.g., "hint", "forecast", "risk").
    advice : str
        Human-readable recommendation or observation.
    confidence : float
        Confidence in [0.0, 1.0].
    applied : bool, default=False
        Whether the system acted on this advice.
    rationale : str | None, default=None
        Reasoning behind the advice.
    evidence_ids : list[str], default=[]
        References to prior evidence or events.
    patch : dict | None, default=None
        Used in interventive modes to propose small input edits.
    """

    kind: str
    advice: str
    confidence: float
    applied: bool = False
    rationale: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    patch: Optional[Dict[str, Any]] = None
    target: str = "input"  # what the advice is pointing at (input/tool/plan)
    scope: str = "episode"  # temporal scope: episode|step
    blocking: bool = False   # set True for veto-style guidance

    # Ensure confidence stays in range for numerical safety
    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        # normalize kind to the canonical Enum if possible (without raising)
        try:
            DirectiveKind(self.kind)
        except ValueError:
            if self.blocking:
                self.kind = DirectiveKind.VETO.value

# Intuition policy interface

class Intuition(Protocol):
    """
    Base protocol for intuition policies.

    Implementations can inspect the reasoning state and emit an `IntuitionEvent`.
    """

    mode: IntuitionMode

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        """Analyze current context and optionally return a structured hint."""
        ...


class NullIntuition:
    """
    Default no-op intuition.

    Used when intuition is disabled or unconfigured.
    Always returns `None` while preserving call-site symmetry.
    """

    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        return None


class DirectedIntuition(Intuition):
    """Helper base with ergonomic constructors for directional events."""

    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def hint(
        self,
        *,
        advice: str,
        confidence: float = 0.5,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "input",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.HINT.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            target=target,
            scope=scope,
        )

    def intervene(
        self,
        *,
        advice: str,
        patch: Dict[str, Any],
        confidence: float = 0.6,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "input",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.INTERVENTION.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            patch=patch,
            target=target,
            scope=scope,
        )

    def veto(
        self,
        *,
        advice: str,
        confidence: float = 0.8,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "plan",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.VETO.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            blocking=True,
            target=target,
            scope=scope,
        )
