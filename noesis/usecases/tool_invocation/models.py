"""Use-case input models for protocol-first tool invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from noesis.domain.tool_contract import (
    ExecutionContext,
    GovernanceContext,
    PayloadRedactionPolicy,
    SecurityContext,
    ToolIdentity,
    ToolProtocol,
)


@dataclass(frozen=True, slots=True)
class ToolInvocationInput:
    """Raw invocation input to be validated and prepared by the use-case layer."""

    run_id: str
    request_id: str
    protocol: ToolProtocol
    tool: ToolIdentity
    raw_payload: Mapping[str, Any]
    execution: ExecutionContext
    security: SecurityContext
    governance: GovernanceContext
    redaction_policy: PayloadRedactionPolicy | None = None
    draft_id: str | None = None


__all__ = ["ToolInvocationInput"]
