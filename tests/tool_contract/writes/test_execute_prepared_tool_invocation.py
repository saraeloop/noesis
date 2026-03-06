from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from noesis.domain.tool_contract import (
    ApprovalDecisionBindingError,
    ApprovalDecisionRequiredError,
    ApprovalDecisionStatus,
    EffectKind,
    ExecutionContext,
    ExecutionStatus,
    GovernanceContext,
    IdempotencyDecision,
    IdempotencyEvaluation,
    PayloadEvidence,
    PreflightBinding,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    PreparedToolInvocationNotFoundError,
    RiskTier,
    SecurityContext,
    ToolApprovalDecision,
    ToolExecutionResult,
    ToolIdentity,
    ToolProtocol,
)
from noesis.domain.tool_contract.event_names import (
    TOOL_APPROVED,
    TOOL_EXECUTION_STARTED,
    TOOL_EXECUTION_SUCCEEDED,
    TOOL_REPLAYED,
)
from noesis.domain.tool_contract.reason_codes import IDEMPOTENCY_REPLAY
from noesis.usecases.tool_invocation import execute_prepared_tool_invocation


class InMemoryPreparedRepository:
    def __init__(self, invocations: list[PreparedToolInvocation] | None = None) -> None:
        self.by_identity = {
            (invocation.run_id, invocation.draft_id): invocation for invocation in invocations or []
        }

    def save(self, invocation: PreparedToolInvocation) -> None:
        self.by_identity[(invocation.run_id, invocation.draft_id)] = invocation

    def load(self, *, run_id: str, draft_id: str) -> PreparedToolInvocation | None:
        return self.by_identity.get((run_id, draft_id))


class InMemoryApprovalRepository:
    def __init__(self, decisions: list[ToolApprovalDecision] | None = None) -> None:
        self.by_identity = {(decision.run_id, decision.draft_id): decision for decision in decisions or []}

    def save(self, decision: ToolApprovalDecision) -> None:
        self.by_identity[(decision.run_id, decision.draft_id)] = decision

    def load(self, *, run_id: str, draft_id: str) -> ToolApprovalDecision | None:
        return self.by_identity.get((run_id, draft_id))


class StaticIdempotencyStore:
    def __init__(self, evaluation: IdempotencyEvaluation) -> None:
        self.evaluation = evaluation
        self.recorded: list[tuple[PreparedToolInvocation, ToolExecutionResult]] = []

    def evaluate(self, *, invocation: PreparedToolInvocation) -> IdempotencyEvaluation:
        return self.evaluation

    def record(
        self,
        *,
        invocation: PreparedToolInvocation,
        result: ToolExecutionResult,
    ) -> None:
        self.recorded.append((invocation, result))


class RecordingDispatch:
    def __init__(self, result: ToolExecutionResult) -> None:
        self.result = result
        self.calls: list[PreparedToolInvocation] = []

    def execute(self, *, invocation: PreparedToolInvocation) -> ToolExecutionResult:
        self.calls.append(invocation)
        return self.result


@dataclass
class RecordingEventRecorder:
    events: list[tuple[str, dict[str, Any]]]

    def record(
        self,
        *,
        run_id: str,
        request_id: str,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        self.events.append((event_name, dict(payload)))


def test_execute_prepared_tool_invocation_rejects_unknown_identity() -> None:
    with pytest.raises(PreparedToolInvocationNotFoundError):
        execute_prepared_tool_invocation(
            run_id="run-missing",
            draft_id="draft-missing",
            prepared_repository=InMemoryPreparedRepository(),
            approval_repository=InMemoryApprovalRepository(),
            idempotency_store=StaticIdempotencyStore(
                IdempotencyEvaluation(decision=IdempotencyDecision.NEW, fingerprint="sha256:req")
            ),
            dispatch=RecordingDispatch(_success_result()),
            event_recorder=RecordingEventRecorder(events=[]),
        )


def test_execute_prepared_tool_invocation_rejects_missing_approval() -> None:
    prepared = _prepared_invocation()
    dispatch = RecordingDispatch(_success_result(request_id=prepared.request_id))

    with pytest.raises(ApprovalDecisionRequiredError):
        execute_prepared_tool_invocation(
            run_id=prepared.run_id,
            draft_id=prepared.draft_id or "",
            prepared_repository=InMemoryPreparedRepository([prepared]),
            approval_repository=InMemoryApprovalRepository(),
            idempotency_store=StaticIdempotencyStore(
                IdempotencyEvaluation(decision=IdempotencyDecision.NEW, fingerprint=prepared.payload.request_fingerprint)
            ),
            dispatch=dispatch,
            event_recorder=RecordingEventRecorder(events=[]),
        )

    assert dispatch.calls == []


def test_execute_prepared_tool_invocation_rejects_approval_fingerprint_mismatch() -> None:
    prepared = _prepared_invocation()
    approval = _approved_decision(prepared, reviewed_fingerprint="sha256:wrong")
    dispatch = RecordingDispatch(_success_result(request_id=prepared.request_id))

    with pytest.raises(ApprovalDecisionBindingError, match="fingerprint"):
        execute_prepared_tool_invocation(
            run_id=prepared.run_id,
            draft_id=prepared.draft_id or "",
            prepared_repository=InMemoryPreparedRepository([prepared]),
            approval_repository=InMemoryApprovalRepository([approval]),
            idempotency_store=StaticIdempotencyStore(
                IdempotencyEvaluation(decision=IdempotencyDecision.NEW, fingerprint=prepared.payload.request_fingerprint)
            ),
            dispatch=dispatch,
            event_recorder=RecordingEventRecorder(events=[]),
        )

    assert dispatch.calls == []


def test_execute_prepared_tool_invocation_rejects_approval_impact_hash_mismatch() -> None:
    prepared = _prepared_invocation()
    approval = _approved_decision(prepared, impact_hash="sha256:wrong-impact")
    dispatch = RecordingDispatch(_success_result(request_id=prepared.request_id))

    with pytest.raises(ApprovalDecisionBindingError, match="impact hash"):
        execute_prepared_tool_invocation(
            run_id=prepared.run_id,
            draft_id=prepared.draft_id or "",
            prepared_repository=InMemoryPreparedRepository([prepared]),
            approval_repository=InMemoryApprovalRepository([approval]),
            idempotency_store=StaticIdempotencyStore(
                IdempotencyEvaluation(decision=IdempotencyDecision.NEW, fingerprint=prepared.payload.request_fingerprint)
            ),
            dispatch=dispatch,
            event_recorder=RecordingEventRecorder(events=[]),
        )

    assert dispatch.calls == []


def test_execute_prepared_tool_invocation_dispatches_approved_prepared_intent() -> None:
    prepared = _prepared_invocation()
    approval = _approved_decision(prepared)
    store = StaticIdempotencyStore(
        IdempotencyEvaluation(decision=IdempotencyDecision.NEW, fingerprint=prepared.payload.request_fingerprint)
    )
    dispatch = RecordingDispatch(_success_result(request_id=prepared.request_id))
    recorder = RecordingEventRecorder(events=[])

    result = execute_prepared_tool_invocation(
        run_id=prepared.run_id,
        draft_id=prepared.draft_id or "",
        prepared_repository=InMemoryPreparedRepository([prepared]),
        approval_repository=InMemoryApprovalRepository([approval]),
        idempotency_store=store,
        dispatch=dispatch,
        event_recorder=recorder,
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert dispatch.calls == [prepared]
    assert store.recorded == [(prepared, result)]
    assert [event_name for event_name, _ in recorder.events] == [
        TOOL_APPROVED,
        TOOL_EXECUTION_STARTED,
        TOOL_EXECUTION_SUCCEEDED,
    ]


def test_execute_prepared_tool_invocation_replays_without_dispatch() -> None:
    prepared = _prepared_invocation()
    approval = _approved_decision(prepared)
    dispatch = RecordingDispatch(_success_result(request_id=prepared.request_id))
    recorder = RecordingEventRecorder(events=[])

    result = execute_prepared_tool_invocation(
        run_id=prepared.run_id,
        draft_id=prepared.draft_id or "",
        prepared_repository=InMemoryPreparedRepository([prepared]),
        approval_repository=InMemoryApprovalRepository([approval]),
        idempotency_store=StaticIdempotencyStore(
            IdempotencyEvaluation(
                decision=IdempotencyDecision.REPLAY,
                fingerprint=prepared.payload.request_fingerprint,
                replayed_execution_id="exec-existing",
            )
        ),
        dispatch=dispatch,
        event_recorder=recorder,
    )

    assert result.status is ExecutionStatus.REPLAYED
    assert result.reason_code == IDEMPOTENCY_REPLAY
    assert dispatch.calls == []
    assert [event_name for event_name, _ in recorder.events] == [TOOL_APPROVED, TOOL_REPLAYED]


def _prepared_invocation() -> PreparedToolInvocation:
    return PreparedToolInvocation(
        run_id="run-1",
        request_id="req-1",
        protocol=ToolProtocol.SUBPROCESS,
        tool=ToolIdentity(namespace="repo", name="write_file", version="1"),
        payload=PayloadEvidence(
            normalized_payload={"path": "README.md", "content": "hello"},
            redacted_payload={"path": "README.md", "content": "hello"},
            request_fingerprint="sha256:req-1",
            redaction_applied=False,
        ),
        execution=ExecutionContext(timeout_ms=1_000, retry_limit=1, idempotency_key="idem-1"),
        security=SecurityContext(
            principal_id="user:123",
            scopes=("repo:write",),
            policy_scope="repo/main",
            authn_method="oauth",
            credential_ref="secret:repo",
        ),
        governance=GovernanceContext(
            effect_kind=EffectKind.WRITE,
            risk_tier=RiskTier.HIGH,
            candidate_id="cand-1",
            requires_approval=True,
            tags=("repo", "write"),
        ),
        status=PreparedInvocationStatus.PENDING_APPROVAL,
        draft_id="draft:run-1:req-1",
        preflight=PreflightBinding(impact_hash="sha256:impact"),
    )


def _approved_decision(
    prepared: PreparedToolInvocation,
    *,
    reviewed_fingerprint: str | None = None,
    impact_hash: str | None = None,
) -> ToolApprovalDecision:
    return ToolApprovalDecision(
        decision_id="decision-1",
        run_id=prepared.run_id,
        request_id=prepared.request_id,
        candidate_id=prepared.governance.candidate_id,
        draft_id=prepared.draft_id,
        status=ApprovalDecisionStatus.APPROVED,
        reviewed_fingerprint=reviewed_fingerprint or prepared.payload.request_fingerprint,
        impact_hash=impact_hash or (prepared.preflight.impact_hash if prepared.preflight else None),
        approver_id="approver:1",
        approval_token_ref="approval:token",
    )


def _success_result(*, request_id: str = "req-1") -> ToolExecutionResult:
    return ToolExecutionResult(
        request_id=request_id,
        execution_id="exec-1",
        status=ExecutionStatus.SUCCEEDED,
        output={"ok": True},
    )
