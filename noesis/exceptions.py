"""Custom exception hierarchy for Noēsis."""

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
