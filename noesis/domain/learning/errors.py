"""Domain errors for learning causality and contract enforcement."""

from __future__ import annotations

__all__ = [
    "LearnCausalityError",
    "MissingCausalLinkError",
]


class LearnCausalityError(RuntimeError):
    """Base error for learning causality contract violations."""


class MissingCausalLinkError(LearnCausalityError):
    """Raised when learning evidence is emitted without a causal parent link."""

