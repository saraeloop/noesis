"""
Pre-act action gating use case.

Evaluates a pending action candidate against governance policy, emits trace
events, and returns a decision suitable for side-effectful adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, Literal, Sequence
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.faculties.governance import (
    GovernanceDecision,
    GovernanceFailurePolicy,
    GovernanceMode,
    GovernanceResult,
    PreActGovernor,
    with_governance_context,
)
from noesis.domain.planner.interfaces import EventBus
from noesis.domain.state import PlanStep
from noesis.diagnostics.validators import is_valid_sha256_state_hash
from noesis.runtime.artifacts.ids import action_candidate_uuid, governance_uuid


@dataclass(frozen=True, slots=True)
class ActionGateResult:
    """Outcome of a pre-act action governance gate."""

    candidate: ActionCandidate
    candidate_event_id: UUID
    governance_result: GovernanceResult | None
    governance_event_id: UUID | None
    should_execute: bool
    terminal_outcome: Literal["none", "vetoed", "error"] = "none"
    reason: str | None = None


def govern_pre_act_action(
    *,
    goal: str,
    plan: Sequence[PlanStep],
    candidate: ActionCandidate,
    event_bus: EventBus,
    episode_id: str,
    governance_policy: PreActGovernor | None,
    governance_mode: GovernanceMode,
    failure_policy: GovernanceFailurePolicy | None,
    timeout_ms: int | None,
    caused_by: UUID | None,
) -> ActionGateResult:
    """
    Emit an action candidate event and evaluate governance for a pending action.

    Returns a gate result indicating whether execution should proceed.
    """
    _validate_state_ref(candidate.state_ref)
    _validate_state_hash(candidate.state_hash)
    candidate = _ensure_candidate_id(candidate, episode_id=episode_id)
    candidate_event_id = event_bus.emit_action_candidate(candidate=candidate, caused_by=caused_by)

    mode = governance_mode or GovernanceMode.OFF
    if governance_policy is None or mode is GovernanceMode.OFF:
        return ActionGateResult(
            candidate=candidate,
            candidate_event_id=candidate_event_id,
            governance_result=None,
            governance_event_id=None,
            should_execute=True,
        )

    failure_policy = failure_policy or GovernanceFailurePolicy.default_for(mode)
    governance_error: Dict[str, object] | None = None
    try:
        raw_result = _evaluate_governance(
            policy=governance_policy,
            goal=goal,
            plan=plan,
            candidate=candidate,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:  # noqa: BLE001
        governance_error = _governance_error_payload(exc)
        raw_result = GovernanceResult(
            decision=GovernanceDecision.AUDIT,
            rule_id="rule:governance.failure",
            score=0.0,
            message="Governance evaluation failed",
            policy_id="policy:runtime.governance",
            policy_version="1.0.0",
            policy_kind="rules",
            details={"error": governance_error},
        )

    governance_result = with_governance_context(
        _with_stable_governance_id(raw_result, episode_id=episode_id),
        mode=mode,
        failure_policy=failure_policy,
        enforced=(
            mode is GovernanceMode.ENFORCE
            and raw_result.decision is GovernanceDecision.VETO
            and governance_error is None
        ),
        error=governance_error,
    )
    governance_event_id = event_bus.emit_governance(
        result=governance_result,
        caused_by=candidate_event_id,
    )

    if governance_error and mode is GovernanceMode.ENFORCE and failure_policy is GovernanceFailurePolicy.FAIL_CLOSED:
        return ActionGateResult(
            candidate=candidate,
            candidate_event_id=candidate_event_id,
            governance_result=governance_result,
            governance_event_id=governance_event_id,
            should_execute=False,
            terminal_outcome="error",
            reason="governance_failure",
        )
    if governance_result.decision is GovernanceDecision.VETO and mode is GovernanceMode.ENFORCE:
        return ActionGateResult(
            candidate=candidate,
            candidate_event_id=candidate_event_id,
            governance_result=governance_result,
            governance_event_id=governance_event_id,
            should_execute=False,
            terminal_outcome="vetoed",
            reason=governance_result.rule_id,
        )

    return ActionGateResult(
        candidate=candidate,
        candidate_event_id=candidate_event_id,
        governance_result=governance_result,
        governance_event_id=governance_event_id,
        should_execute=True,
    )


def _ensure_candidate_id(candidate: ActionCandidate, *, episode_id: str) -> ActionCandidate:
    if candidate.id:
        return candidate
    fingerprint = candidate.canonical_json()
    candidate_id = str(action_candidate_uuid(episode_id, fingerprint))
    return candidate.with_id(candidate_id)


def _validate_state_ref(state_ref: str) -> None:
    if not state_ref:
        raise ValueError("ActionCandidate.state_ref is required for auditability")


def _validate_state_hash(state_hash: str) -> None:
    if not state_hash:
        raise ValueError(
            "ActionCandidate.state_hash is required (expected sha256:<64 lowercase hex>)"
        )
    if not is_valid_sha256_state_hash(state_hash):
        raise ValueError(
            "ActionCandidate.state_hash must be 'sha256:<64 lowercase hex>', "
            f"got: {state_hash!r}"
        )


def _with_stable_governance_id(result: GovernanceResult, episode_id: str) -> GovernanceResult:
    rule_token = result.rule_id or result.policy_id or result.decision.value
    stable_id = governance_uuid(episode_id, rule_token)
    return replace(result, decision_id=stable_id)


def _evaluate_governance(
    *,
    policy: PreActGovernor,
    goal: str,
    plan: Sequence[PlanStep],
    candidate: ActionCandidate | None = None,
    timeout_ms: int | None,
) -> GovernanceResult:
    evaluator = _resolve_action_evaluator(policy, candidate=candidate)
    if timeout_ms is None:
        return evaluator(goal=goal, plan=plan)
    timeout_sec = max(timeout_ms, 1) / 1000.0
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(evaluator, goal=goal, plan=plan)
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeoutError as exc:
            raise TimeoutError("governance_timeout") from exc


def _resolve_action_evaluator(
    policy: PreActGovernor,
    *,
    candidate: ActionCandidate | None,
) -> Callable[..., GovernanceResult]:
    evaluate_action = getattr(policy, "evaluate_action", None)
    if callable(evaluate_action) and candidate is not None:
        return lambda *, goal, plan: evaluate_action(goal=goal, plan=plan, action=candidate)
    return lambda *, goal, plan: policy.evaluate(goal=goal, plan=plan)


def _governance_error_payload(exc: Exception) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
    if isinstance(exc, TimeoutError):
        payload["timeout"] = True
    return payload
