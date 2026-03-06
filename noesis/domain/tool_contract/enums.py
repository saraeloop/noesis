"""Enums for the protocol-first tool contract."""

from __future__ import annotations

from enum import Enum


class ToolProtocol(str, Enum):
    """Supported tool transport protocols."""

    SUBPROCESS = "subprocess"
    HTTP = "http"
    MCP = "mcp"


class EffectKind(str, Enum):
    """Whether the invocation is observational or side-effectful."""

    READ = "read"
    WRITE = "write"


class RiskTier(str, Enum):
    """Risk classification used for governance and policy decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PreparedInvocationStatus(str, Enum):
    """Lifecycle states for prepared tool intents."""

    PREPARED = "prepared"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"


class ApprovalDecisionStatus(str, Enum):
    """Terminal statuses for an approval decision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionStatus(str, Enum):
    """Terminal statuses for tool execution results."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REPLAYED = "replayed"


class IdempotencyDecision(str, Enum):
    """Result of evaluating an idempotency key against prior execution state."""

    NEW = "new"
    REPLAY = "replay"
    CONFLICT = "conflict"


__all__ = [
    "ApprovalDecisionStatus",
    "EffectKind",
    "ExecutionStatus",
    "IdempotencyDecision",
    "PreparedInvocationStatus",
    "RiskTier",
    "ToolProtocol",
]
