from __future__ import annotations

from noesis.domain.tool_contract import (
    ApprovalDecisionStatus,
    EffectKind,
    ExecutionContext,
    ExecutionStatus,
    GovernanceContext,
    PayloadEvidence,
    PreflightBinding,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    RiskTier,
    SecurityContext,
    TOOL_CONTRACT_SCHEMA_VERSION,
    ToolApprovalDecision,
    ToolExecutionResult,
    ToolIdentity,
    ToolProtocol,
)


def test_core_artifact_models_capture_contract_shape() -> None:
    tool = ToolIdentity(namespace="repo", name="write_file", version="1")
    payload = PayloadEvidence(
        normalized_payload={"path": "README.md", "content": "hello"},
        redacted_payload={"path": "README.md", "content": "[REDACTED]"},
        request_fingerprint="sha256:abc",
        redaction_applied=True,
    )
    execution = ExecutionContext(timeout_ms=5000, retry_limit=1, idempotency_key="idem-1")
    security = SecurityContext(
        principal_id="user:123",
        scopes=("repo:write",),
        policy_scope="repo/main",
        authn_method="oauth",
        credential_ref="secret:repo-token",
    )
    governance = GovernanceContext(
        effect_kind=EffectKind.WRITE,
        risk_tier=RiskTier.HIGH,
        candidate_id="cand-1",
        requires_approval=True,
        tags=("repo", "write"),
    )

    prepared = PreparedToolInvocation(
        run_id="run-1",
        request_id="req-1",
        protocol=ToolProtocol.SUBPROCESS,
        tool=tool,
        payload=payload,
        execution=execution,
        security=security,
        governance=governance,
        status=PreparedInvocationStatus.PENDING_APPROVAL,
        draft_id="draft-1",
        preflight=PreflightBinding(impact_hash="sha256:impact"),
    )
    approval = ToolApprovalDecision(
        decision_id="decision-1",
        run_id=prepared.run_id,
        request_id=prepared.request_id,
        candidate_id=governance.candidate_id,
        draft_id=prepared.draft_id,
        status=ApprovalDecisionStatus.APPROVED,
        reviewed_fingerprint=prepared.payload.request_fingerprint,
        impact_hash=prepared.preflight.impact_hash if prepared.preflight else None,
        approval_token_ref="approval:token",
    )
    result = ToolExecutionResult(
        request_id=prepared.request_id,
        execution_id="exec-1",
        status=ExecutionStatus.SUCCEEDED,
        output={"exit_code": 0},
    )

    assert prepared.schema_version == TOOL_CONTRACT_SCHEMA_VERSION
    assert prepared.run_id == "run-1"
    assert approval.status is ApprovalDecisionStatus.APPROVED
    assert approval.reviewed_fingerprint == "sha256:abc"
    assert approval.impact_hash == "sha256:impact"
    assert result.status is ExecutionStatus.SUCCEEDED
    assert prepared.governance.requires_approval is True
    assert prepared.payload.request_fingerprint == "sha256:abc"
