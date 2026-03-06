"""Execute prepared tool invocations by durable identity."""

from __future__ import annotations

from noesis.domain.tool_contract import (
    ApprovalDecisionBindingError,
    ApprovalDecisionRequiredError,
    ApprovalDecisionStatus,
    ExecutionStatus,
    IdempotencyDecision,
    PreparedToolInvocationNotFoundError,
    ToolExecutionResult,
)
from noesis.domain.tool_contract.event_names import (
    TOOL_APPROVED,
    TOOL_EXECUTION_FAILED,
    TOOL_EXECUTION_STARTED,
    TOOL_EXECUTION_SUCCEEDED,
    TOOL_REPLAYED,
)
from noesis.domain.tool_contract.reason_codes import IDEMPOTENCY_CONFLICT, IDEMPOTENCY_REPLAY

from .ports import (
    ApprovalDecisionRepositoryPort,
    IdempotencyStorePort,
    PreparedInvocationRepositoryPort,
    ToolDispatchPort,
    ToolEventRecorderPort,
)


def execute_prepared_tool_invocation(
    *,
    run_id: str,
    draft_id: str,
    prepared_repository: PreparedInvocationRepositoryPort,
    approval_repository: ApprovalDecisionRepositoryPort,
    idempotency_store: IdempotencyStorePort,
    dispatch: ToolDispatchPort,
    event_recorder: ToolEventRecorderPort,
) -> ToolExecutionResult:
    """Load, validate, and execute a prepared invocation by durable identity."""

    prepared = prepared_repository.load(run_id=run_id, draft_id=draft_id)
    if prepared is None:
        raise PreparedToolInvocationNotFoundError(
            f"prepared invocation not found for run_id={run_id!r}, draft_id={draft_id!r}"
        )

    if prepared.governance.requires_approval:
        decision = approval_repository.load(run_id=run_id, draft_id=draft_id)
        if decision is None or decision.status is not ApprovalDecisionStatus.APPROVED:
            raise ApprovalDecisionRequiredError(
                f"approved decision required for run_id={run_id!r}, draft_id={draft_id!r}"
            )
        if decision.request_id != prepared.request_id:
            raise ApprovalDecisionBindingError("approval decision request_id does not match prepared intent")
        if decision.reviewed_fingerprint != prepared.payload.request_fingerprint:
            raise ApprovalDecisionBindingError("approval decision fingerprint does not match prepared intent")
        if prepared.preflight is not None and decision.impact_hash != prepared.preflight.impact_hash:
            raise ApprovalDecisionBindingError("approval decision impact hash does not match prepared intent")
        event_recorder.record(
            run_id=run_id,
            request_id=prepared.request_id,
            event_name=TOOL_APPROVED,
            payload={"draft_id": draft_id, "decision_id": decision.decision_id},
        )

    evaluation = idempotency_store.evaluate(invocation=prepared)
    if evaluation.decision is IdempotencyDecision.REPLAY:
        result = ToolExecutionResult(
            request_id=prepared.request_id,
            execution_id=evaluation.replayed_execution_id or f"exec:replay:{draft_id}",
            status=ExecutionStatus.REPLAYED,
            reason_code=IDEMPOTENCY_REPLAY,
            replayed_from_execution_id=evaluation.replayed_execution_id,
            preflight=prepared.preflight,
        )
        event_recorder.record(
            run_id=run_id,
            request_id=prepared.request_id,
            event_name=TOOL_REPLAYED,
            payload={"draft_id": draft_id, "execution_id": result.execution_id},
        )
        return result
    if evaluation.decision is IdempotencyDecision.CONFLICT:
        result = ToolExecutionResult(
            request_id=prepared.request_id,
            execution_id=evaluation.replayed_execution_id or f"exec:conflict:{draft_id}",
            status=ExecutionStatus.FAILED,
            reason_code=IDEMPOTENCY_CONFLICT,
            replayed_from_execution_id=evaluation.replayed_execution_id,
            preflight=prepared.preflight,
        )
        event_recorder.record(
            run_id=run_id,
            request_id=prepared.request_id,
            event_name=TOOL_EXECUTION_FAILED,
            payload={"draft_id": draft_id, "reason_code": IDEMPOTENCY_CONFLICT},
        )
        return result

    event_recorder.record(
        run_id=run_id,
        request_id=prepared.request_id,
        event_name=TOOL_EXECUTION_STARTED,
        payload={"draft_id": draft_id, "candidate_id": prepared.governance.candidate_id},
    )
    result = dispatch.execute(invocation=prepared)
    idempotency_store.record(invocation=prepared, result=result)
    event_recorder.record(
        run_id=run_id,
        request_id=prepared.request_id,
        event_name=(
            TOOL_EXECUTION_SUCCEEDED
            if result.status is ExecutionStatus.SUCCEEDED
            else TOOL_EXECUTION_FAILED
        ),
        payload={"draft_id": draft_id, "execution_id": result.execution_id, "reason_code": result.reason_code},
    )
    return result


__all__ = ["execute_prepared_tool_invocation"]
