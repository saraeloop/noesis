from __future__ import annotations

from noesis.domain.tool_contract import IdempotencyDecision, evaluate_idempotency


def test_idempotency_evaluation_distinguishes_new_replay_and_conflict() -> None:
    created = evaluate_idempotency(
        incoming_fingerprint="sha256:req-a",
        existing_fingerprint=None,
    )
    replayed = evaluate_idempotency(
        incoming_fingerprint="sha256:req-a",
        existing_fingerprint="sha256:req-a",
        existing_execution_id="exec-1",
    )
    conflict = evaluate_idempotency(
        incoming_fingerprint="sha256:req-b",
        existing_fingerprint="sha256:req-a",
        existing_execution_id="exec-1",
    )

    assert created.decision is IdempotencyDecision.NEW
    assert replayed.decision is IdempotencyDecision.REPLAY
    assert replayed.replayed_execution_id == "exec-1"
    assert conflict.decision is IdempotencyDecision.CONFLICT
