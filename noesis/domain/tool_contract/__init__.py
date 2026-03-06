"""Protocol-first tool contract domain package."""

from .enums import (
    ApprovalDecisionStatus,
    EffectKind,
    ExecutionStatus,
    IdempotencyDecision,
    PreparedInvocationStatus,
    RiskTier,
    ToolProtocol,
)
from .errors import (
    AmbiguousPreparedToolInvocationError,
    ApprovalDecisionBindingError,
    ApprovalDecisionRequiredError,
    PreparedToolInvocationNotFoundError,
    ToolAuthenticationError,
    ToolAuthorizationError,
    ToolContractError,
)
from .event_names import ALL_EVENT_NAMES
from .fingerprints import canonical_json, fingerprint_payload, fingerprint_prepared_invocation
from .idempotency import IdempotencyEvaluation, IdempotencyScope, evaluate_idempotency
from .models import (
    ExecutionContext,
    GovernanceContext,
    PayloadEvidence,
    PreflightBinding,
    PreparedToolInvocation,
    SecurityContext,
    TOOL_CONTRACT_SCHEMA_VERSION,
    ToolApprovalDecision,
    ToolExecutionResult,
    ToolIdentity,
)
from .reason_codes import ALL_REASON_CODES
from .redaction import PayloadRedactionPolicy, REDACTED_VALUE, apply_redaction, build_payload_evidence

__all__ = [
    "ALL_EVENT_NAMES",
    "ALL_REASON_CODES",
    "AmbiguousPreparedToolInvocationError",
    "ApprovalDecisionBindingError",
    "ApprovalDecisionRequiredError",
    "ApprovalDecisionStatus",
    "EffectKind",
    "ExecutionContext",
    "ExecutionStatus",
    "GovernanceContext",
    "IdempotencyDecision",
    "IdempotencyEvaluation",
    "IdempotencyScope",
    "PayloadEvidence",
    "PayloadRedactionPolicy",
    "PreflightBinding",
    "PreparedToolInvocationNotFoundError",
    "PreparedInvocationStatus",
    "PreparedToolInvocation",
    "REDACTED_VALUE",
    "RiskTier",
    "SecurityContext",
    "TOOL_CONTRACT_SCHEMA_VERSION",
    "ToolAuthenticationError",
    "ToolApprovalDecision",
    "ToolAuthorizationError",
    "ToolContractError",
    "ToolExecutionResult",
    "ToolIdentity",
    "ToolProtocol",
    "apply_redaction",
    "build_payload_evidence",
    "canonical_json",
    "evaluate_idempotency",
    "fingerprint_payload",
    "fingerprint_prepared_invocation",
]
