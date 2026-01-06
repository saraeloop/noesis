"""
Actuation port contracts for governed side effects.

These interfaces provide a stable boundary for executing side-effectful actions
behind pre-act governance without exposing internal implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from noesis.context import RuntimeContext

__all__ = ["ActuationPort", "GovernedActRequest"]


@dataclass(frozen=True, slots=True)
class GovernedActRequest:
    """Request payload for governed actuation."""

    goal: str
    kind: str
    payload: Mapping[str, Any]
    seed: int = 0
    tags: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] | None = None
    risk_tags: tuple[str, ...] | None = None
    redaction: Mapping[str, Any] | None = None
    determinism: object | None = None


class ActuationPort(Protocol):
    """Port for executing governed actions."""

    __api_version__: str = "actuation/1.0"

    def governed_act(self, request: GovernedActRequest, *, context: RuntimeContext) -> Any:
        """Execute a governed action and return the result."""
