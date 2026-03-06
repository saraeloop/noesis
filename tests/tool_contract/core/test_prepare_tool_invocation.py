from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from noesis.domain.tool_contract import (
    EffectKind,
    ExecutionContext,
    GovernanceContext,
    PayloadRedactionPolicy,
    PreflightBinding,
    PreparedInvocationStatus,
    RiskTier,
    SecurityContext,
    ToolIdentity,
    ToolProtocol,
)
from noesis.domain.tool_contract.event_names import (
    ACTION_CANDIDATE_EMITTED,
    TOOL_APPROVAL_PENDING,
    TOOL_AUTHN_PASSED,
    TOOL_AUTHZ_PASSED,
    TOOL_DRAFT_CREATED,
    TOOL_PREFLIGHT_COMPUTED,
    TOOL_REQUESTED,
    TOOL_VALIDATED,
)
from noesis.usecases.tool_invocation import ToolInvocationInput, prepare_tool_invocation


class StaticNormalizer:
    def __init__(self, normalized_payload: Mapping[str, Any]) -> None:
        self.normalized_payload = dict(normalized_payload)

    def validate_and_normalize(
        self,
        *,
        protocol: ToolProtocol,
        tool: ToolIdentity,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return self.normalized_payload


class PassthroughAuthenticator:
    def authenticate(self, *, security: SecurityContext) -> SecurityContext:
        return security


class AllowAuthorizer:
    def authorize(
        self,
        *,
        request: ToolInvocationInput,
        security: SecurityContext,
    ) -> None:
        return None


class StaticCandidateEmitter:
    def emit_candidate(
        self,
        *,
        request: ToolInvocationInput,
        normalized_payload: Mapping[str, Any],
        candidate_id: str | None,
    ) -> str:
        return candidate_id or "cand-generated"


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


class InMemoryPreparedRepository:
    def __init__(self) -> None:
        self.saved = []
        self.by_identity = {}

    def save(self, invocation) -> None:
        self.saved.append(invocation)
        self.by_identity[(invocation.run_id, invocation.draft_id)] = invocation

    def load(self, *, run_id: str, draft_id: str):
        return self.by_identity.get((run_id, draft_id))


class StaticPreflight:
    def __init__(self, binding: PreflightBinding) -> None:
        self.binding = binding

    def compute(self, *, invocation) -> PreflightBinding | None:
        return self.binding


def test_prepare_tool_invocation_persists_pending_write_without_execution() -> None:
    request = ToolInvocationInput(
        run_id="run-1",
        request_id="req-1",
        protocol=ToolProtocol.SUBPROCESS,
        tool=ToolIdentity(namespace="repo", name="write_file", version="1"),
        raw_payload={"path": "README.md", "token": "secret"},
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
            candidate_id=None,
            requires_approval=True,
            tags=("repo", "write"),
        ),
        redaction_policy=PayloadRedactionPolicy(redact_fields=("token",)),
    )
    repository = InMemoryPreparedRepository()
    recorder = RecordingEventRecorder(events=[])

    prepared = prepare_tool_invocation(
        request=request,
        normalizer=StaticNormalizer({"path": "README.md", "token": "secret", "mode": "overwrite"}),
        authenticator=PassthroughAuthenticator(),
        authorizer=AllowAuthorizer(),
        candidate_emitter=StaticCandidateEmitter(),
        event_recorder=recorder,
        prepared_repository=repository,
        preflight=StaticPreflight(PreflightBinding(impact_hash="sha256:impact")),
    )

    assert prepared.status is PreparedInvocationStatus.PENDING_APPROVAL
    assert prepared.draft_id == "draft:run-1:req-1"
    assert prepared.governance.candidate_id == "cand-generated"
    assert prepared.preflight == PreflightBinding(impact_hash="sha256:impact")
    assert prepared.payload.normalized_payload == {"path": "README.md", "token": "secret", "mode": "overwrite"}
    assert prepared.payload.redacted_payload["token"] == "[REDACTED]"
    assert repository.load(run_id="run-1", draft_id="draft:run-1:req-1") == prepared
    event_names = [event_name for event_name, _ in recorder.events]
    assert event_names == [
        TOOL_REQUESTED,
        TOOL_VALIDATED,
        TOOL_AUTHN_PASSED,
        TOOL_AUTHZ_PASSED,
        ACTION_CANDIDATE_EMITTED,
        TOOL_PREFLIGHT_COMPUTED,
        TOOL_DRAFT_CREATED,
        TOOL_APPROVAL_PENDING,
    ]
    assert event_names.index(ACTION_CANDIDATE_EMITTED) < event_names.index(TOOL_APPROVAL_PENDING)
    assert recorder.events[event_names.index(ACTION_CANDIDATE_EMITTED)][1]["candidate_id"] == "cand-generated"
    assert recorder.events[event_names.index(TOOL_APPROVAL_PENDING)][1]["candidate_id"] == "cand-generated"
