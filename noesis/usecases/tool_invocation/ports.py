"""Ports for protocol-first tool invocation use cases."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from noesis.domain.tool_contract import (
    IdempotencyEvaluation,
    PreflightBinding,
    PreparedToolInvocation,
    SecurityContext,
    ToolApprovalDecision,
    ToolExecutionResult,
    ToolIdentity,
    ToolProtocol,
)
from .models import ToolInvocationInput


class ToolPayloadNormalizerPort(Protocol):
    """Validate and normalize raw input into canonical payload data."""

    def validate_and_normalize(
        self,
        *,
        protocol: ToolProtocol,
        tool: ToolIdentity,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...


class ToolAuthenticatorPort(Protocol):
    """Authenticate a tool invocation's security context."""

    def authenticate(self, *, security: SecurityContext) -> SecurityContext:
        ...


class ToolAuthorizerPort(Protocol):
    """Authorize a prepared invocation before it is persisted or executed."""

    def authorize(
        self,
        *,
        request: ToolInvocationInput,
        security: SecurityContext,
    ) -> None:
        ...


class ToolCandidateEmitterPort(Protocol):
    """Emit candidate evidence and return the candidate identifier."""

    def emit_candidate(
        self,
        *,
        request: ToolInvocationInput,
        normalized_payload: Mapping[str, Any],
        candidate_id: str | None,
    ) -> str:
        ...


class ToolEventRecorderPort(Protocol):
    """Record canonical tool-contract events."""

    def record(
        self,
        *,
        run_id: str,
        request_id: str,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        ...


class ToolPreflightPort(Protocol):
    """Compute a deterministic preflight binding for a prepared invocation."""

    def compute(self, *, invocation: PreparedToolInvocation) -> PreflightBinding | None:
        ...


class PreparedInvocationRepositoryPort(Protocol):
    """Persist and load prepared tool invocations by run/draft identity."""

    def save(self, invocation: PreparedToolInvocation) -> None:
        ...

    def load(self, *, run_id: str, draft_id: str) -> PreparedToolInvocation | None:
        ...


class ApprovalDecisionRepositoryPort(Protocol):
    """Persist and load approval decisions bound to prepared drafts."""

    def save(self, decision: ToolApprovalDecision) -> None:
        ...

    def load(self, *, run_id: str, draft_id: str) -> ToolApprovalDecision | None:
        ...


class IdempotencyStorePort(Protocol):
    """Evaluate and record idempotent execution state."""

    def evaluate(self, *, invocation: PreparedToolInvocation) -> IdempotencyEvaluation:
        ...

    def record(
        self,
        *,
        invocation: PreparedToolInvocation,
        result: ToolExecutionResult,
    ) -> None:
        ...


class ToolDispatchPort(Protocol):
    """Dispatch a prepared invocation across the side-effect boundary."""

    def execute(self, *, invocation: PreparedToolInvocation) -> ToolExecutionResult:
        ...


__all__ = [
    "ApprovalDecisionRepositoryPort",
    "IdempotencyStorePort",
    "PreparedInvocationRepositoryPort",
    "ToolAuthenticatorPort",
    "ToolAuthorizerPort",
    "ToolCandidateEmitterPort",
    "ToolDispatchPort",
    "ToolEventRecorderPort",
    "ToolPayloadNormalizerPort",
    "ToolPreflightPort",
]
