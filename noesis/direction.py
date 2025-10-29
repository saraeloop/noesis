"""
Direction layer helpers for Noēsis.

Extends the intuition primitives with ergonomic constructors for
interventions, diffs, and veto-style signals.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from .intuition import Intuition, IntuitionEvent, IntuitionMode, StateSnapshot

__all__ = [
    "DirectiveKind",
    "DirectedIntuition",
]


class DirectiveKind(str, Enum):
    """Direction families emitted by intuition policies."""

    HINT = "hint"
    INTERVENTION = "intervention"
    VETO = "veto"


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
