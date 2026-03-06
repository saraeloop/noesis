"""Core artifact models for the protocol-first tool contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .enums import (
    ApprovalDecisionStatus,
    EffectKind,
    ExecutionStatus,
    PreparedInvocationStatus,
    RiskTier,
    ToolProtocol,
)

TOOL_CONTRACT_SCHEMA_VERSION = "tool_contract/1.0.0"


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Stable tool identity independent of the transport protocol."""

    namespace: str
    name: str
    version: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Execution controls attached to a tool invocation."""

    timeout_ms: int
    retry_limit: int
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityContext:
    """Security attributes required for authorization and audit evidence."""

    principal_id: str
    scopes: tuple[str, ...]
    policy_scope: str
    authn_method: str | None = None
    credential_ref: str | None = None


@dataclass(frozen=True, slots=True)
class GovernanceContext:
    """Governance attributes that influence gating and approval behavior."""

    effect_kind: EffectKind
    risk_tier: RiskTier
    candidate_id: str | None
    requires_approval: bool
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PayloadEvidence:
    """Normalized payload evidence safe to persist in artifacts."""

    normalized_payload: Mapping[str, Any]
    redacted_payload: Mapping[str, Any]
    request_fingerprint: str
    redaction_applied: bool


@dataclass(frozen=True, slots=True)
class PreflightBinding:
    """Deterministic binding between reviewed intent and execution-time state."""

    impact_hash: str
    witness: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PreparedToolInvocation:
    """Prepared tool intent that may later be approved and executed."""

    run_id: str
    request_id: str
    protocol: ToolProtocol
    tool: ToolIdentity
    payload: PayloadEvidence
    execution: ExecutionContext
    security: SecurityContext
    governance: GovernanceContext
    status: PreparedInvocationStatus
    schema_version: str = TOOL_CONTRACT_SCHEMA_VERSION
    draft_id: str | None = None
    preflight: PreflightBinding | None = None


@dataclass(frozen=True, slots=True)
class ToolApprovalDecision:
    """Approval or rejection record linked to a prepared tool invocation."""

    decision_id: str
    run_id: str
    request_id: str
    candidate_id: str | None
    draft_id: str | None
    status: ApprovalDecisionStatus
    schema_version: str = TOOL_CONTRACT_SCHEMA_VERSION
    reason_code: str | None = None
    reviewed_fingerprint: str | None = None
    impact_hash: str | None = None
    approver_id: str | None = None
    approval_token_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Terminal execution result for a prepared tool invocation."""

    request_id: str
    execution_id: str
    status: ExecutionStatus
    schema_version: str = TOOL_CONTRACT_SCHEMA_VERSION
    reason_code: str | None = None
    output: Mapping[str, Any] | None = None
    replayed_from_execution_id: str | None = None
    preflight: PreflightBinding | None = None


__all__ = [
    "ExecutionContext",
    "GovernanceContext",
    "PayloadEvidence",
    "PreflightBinding",
    "PreparedToolInvocation",
    "SecurityContext",
    "TOOL_CONTRACT_SCHEMA_VERSION",
    "ToolApprovalDecision",
    "ToolExecutionResult",
    "ToolIdentity",
]
