"""Use case helpers for verification evaluation and outcome mapping."""
from __future__ import annotations

from typing import Literal, Sequence

from noesis.domain.snapshot import Snapshot, SnapshotPolicy
from noesis.domain.verification import (
    Assertion,
    AssertionContext,
    FileContentReader,
    SnapshotPaths,
    VerificationSummary,
)

AdapterResult = Literal["success", "error", "skipped"]
OutcomeStatus = Literal["success", "goal_not_achieved", "success_unverified", "error"]

__all__ = [
    "AdapterResult",
    "OutcomeStatus",
    "compute_outcome",
    "evaluate_verification",
]


def evaluate_verification(
    *,
    verify: Sequence[Assertion] | None,
    pre: Snapshot | None,
    post: Snapshot | None,
    policy: SnapshotPolicy,
    snapshots: SnapshotPaths | None,
    file_reader: FileContentReader | None,
) -> VerificationSummary:
    """
    Evaluate verification assertions and construct the summary payload.

    `verify` is treated as not provided when empty or None.
    """
    if not verify:
        return VerificationSummary(
            provided=False,
            passed=None,
            assertions=(),
            workspace_diff=None,
            snapshots=None,
            policy=policy,
            error=None,
        )
    if pre is None or post is None:
        return VerificationSummary(
            provided=True,
            passed=None,
            assertions=(),
            workspace_diff=None,
            snapshots=None,
            policy=policy,
            error="workspace_unavailable",
        )
    diff = Snapshot.diff(pre, post)
    context = AssertionContext(snapshot=post, diff=diff, file_reader=file_reader)
    results = tuple(assertion.evaluate(context) for assertion in verify)
    passed = all(result.passed for result in results)
    return VerificationSummary(
        provided=True,
        passed=passed,
        assertions=results,
        workspace_diff=diff,
        snapshots=snapshots,
        policy=policy,
        error=None,
    )


def compute_outcome(
    *,
    adapter_result: AdapterResult,
    verification_provided: bool,
    verification_passed: bool | None,
) -> OutcomeStatus:
    """Apply ADR-010 outcome rules with explicit invariants."""
    if adapter_result in {"error", "skipped"}:
        return "error"
    if not verification_provided:
        if verification_passed is not None:
            raise ValueError("verification_passed must be null when verification is not provided")
        return "success_unverified"
    if verification_passed is None:
        raise ValueError("verification_passed must be set when verification is provided")
    return "success" if verification_passed else "goal_not_achieved"
