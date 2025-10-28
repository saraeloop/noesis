"""
Defines the Intuition interface. A lightweight advisory layer
that can analyze the current agent state and emit directional hints.

This layer is model-agnostic and designed for JSON-friendly outputs.
"""

from typing import Any, Dict, Optional, Protocol
from dataclasses import dataclass, field
import abc


@dataclass
class IntuitionEvent:
    """Structured record of an intuition signal."""
    kind: str
    advice: str
    confidence: float
    applied: bool = False
    rationale: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)


class Intuition(Protocol):
    """Interface for intuition policies."""

    @abc.abstractmethod
    def advise(self, state: Dict[str, Any]) -> Optional[IntuitionEvent]:
        """
        Analyze current agent state and optionally return an intuition event.

        Parameters
        ----------
        state : dict
            Snapshot of the agent’s reasoning context (memory, recent tools, etc.)

        Returns
        -------
        Optional[IntuitionEvent]
            Directional hint or None if no advice is triggered.
        """
        ...


class NullIntuition:
    """Baseline intuition that does nothing (Intuition OFF)."""

    def advise(self, state: Dict[str, Any]) -> Optional[IntuitionEvent]:
        return None