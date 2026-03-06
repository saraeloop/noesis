"""Pure idempotency decision helpers for the tool contract."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import IdempotencyDecision


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    """Identity scope used to interpret an idempotency key."""

    principal_id: str
    tool_key: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class IdempotencyEvaluation:
    """Pure decision result for idempotency matching."""

    decision: IdempotencyDecision
    fingerprint: str
    replayed_execution_id: str | None = None


def evaluate_idempotency(
    *,
    incoming_fingerprint: str,
    existing_fingerprint: str | None,
    existing_execution_id: str | None = None,
) -> IdempotencyEvaluation:
    """Determine whether an invocation is new, replayed, or conflicting."""

    if existing_fingerprint is None:
        return IdempotencyEvaluation(
            decision=IdempotencyDecision.NEW,
            fingerprint=incoming_fingerprint,
        )
    if existing_fingerprint == incoming_fingerprint:
        return IdempotencyEvaluation(
            decision=IdempotencyDecision.REPLAY,
            fingerprint=incoming_fingerprint,
            replayed_execution_id=existing_execution_id,
        )
    return IdempotencyEvaluation(
        decision=IdempotencyDecision.CONFLICT,
        fingerprint=incoming_fingerprint,
    )


__all__ = [
    "IdempotencyEvaluation",
    "IdempotencyScope",
    "evaluate_idempotency",
]
