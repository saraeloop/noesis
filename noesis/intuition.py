"""
Intuition layer primitives for Noēsis.

Provides the base protocol and event schema used by advisory policies.
The direction layer builds on top of these primitives to support patches
and vetoes; see `noesis.direction` for interventive helpers.
"""

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

    ADVISORY = "advisory"         # hints only; must be side-effect free
    INTERVENTIVE = "interventive"  # may change inputs/controls; must log patches
    HYBRID = "hybrid"             # hints + selective interventions


# A reasoning snapshot handed to intuition policies.
StateSnapshot: TypeAlias = Dict[str, Any]


@dataclass(slots=True)
class IntuitionEvent:
    """
    Structured record describing an intuition signal.

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

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

        # Normalize the kind when direction helpers are available.
        try:
            from .direction import DirectiveKind  # local import avoids cycle
        except Exception:
            DirectiveKind = None  # type: ignore[assignment]

        if DirectiveKind is not None:
            try:
                DirectiveKind(self.kind)
            except ValueError:
                if self.blocking:
                    self.kind = DirectiveKind.VETO.value


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

    Used when intuition is disabled or unconfigured. Always returns `None`
    while preserving call-site symmetry.
    """

    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        return None
