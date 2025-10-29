"""
Exception hierarchy for Noēsis.

Defines the system’s control boundaries, where reasoning escalates into
explicit failure or veto. These exceptions mark deliberate interruptions
in an agent’s cognitive loop, ensuring that intervention remains safe,
auditable, and intentional.
"""

from __future__ import annotations


class NoesisError(Exception):
    """Base class for framework-level errors."""


class NoesisVeto(NoesisError):
    """Raised when an intuition policy vetoes the episode."""

    def __init__(self, *, advice: str, target: str, scope: str) -> None:
        super().__init__(advice)
        self.advice = advice
        self.target = target
        self.scope = scope
