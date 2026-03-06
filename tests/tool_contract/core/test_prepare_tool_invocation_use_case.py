from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from noesis.domain.tool_contract import (
    EffectKind,
    ExecutionContext,
    GovernanceContext,
    PayloadRedactionPolicy,
    PreparedInvocationStatus,
    RiskTier,
    SecurityContext,
    ToolAuthenticationError,
    ToolAuthorizationError,
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
from noesis.usecases.tool_invocation.models import ToolInvocationInput
from noesis.usecases.tool_invocation.prepare_tool_invocation import prepare_tool_invocation


class _Normalizer:
    def validate_and_normalize(self, *, protocol, tool, payload):
        assert protocol is ToolProtocol.SUBPROCESS
        assert tool.name == "write_file"
        return {"path": "README.md", "body": "hello", "token": "secret"}


class _Authenticator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def authenticate(self, *, security):
        if self.fail:
            raise ToolAuthenticationError("auth failed")
        return security


class _Authorizer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def authorize(self, *, request, security) -> None:
        if self.fail:
            raise ToolAuthorizationError("denied")


class _CandidateEmitter:
    def emit_candidate(self, *, request, normalized_payload, candidate_id):
        return candidate_id or "cand-1"


class _EventRecorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def record(self, *, run_id, request_id, event_name, payload):
        self.events.append(event_name)


class _PreparedRepo:
    def __init__(self) -> None:
        self.saved = None

    def save(self, invocation) -> None:
        self.saved = invocation

    def load(self, *, run_id, draft_id):
        return self.saved


class _Preflight:
    def compute(self, *, invocation):
        from noesis.domain.tool_contract import PreflightBinding

        return PreflightBinding(impact_hash="sha256:impact")


def _request() -> ToolInvocationInput:
    return ToolInvocationInput(
        run_id="run-1",
        request_id="req-1",
        protocol=ToolProtocol.SUBPROCESS,
        tool=ToolIdentity(namespace="repo", name="write_file", version="1"),
        raw_payload={"argv": ["write", "README.md"]},
        execution=ExecutionContext(timeout_ms=1000, retry_limit=0, idempotency_key="idem-1"),
        security=SecurityContext(
            principal_id="user:1",
            scopes=("repo:write",),
            policy_scope="repo/main",
            authn_method="oauth",
            credential_ref="secret:repo-token",
        ),
        governance=GovernanceContext(
            effect_kind=EffectKind.WRITE,
            risk_tier=RiskTier.HIGH,
            candidate_id=None,
            requires_approval=True,
            tags=("repo",),
        ),
        redaction_policy=PayloadRedactionPolicy(redact_fields=("token",)),
    )


def test_prepare_tool_invocation_persists_pending_approval_without_side_effect_dispatch() -> None:
    recorder = _EventRecorder()
    repo = _PreparedRepo()

    prepared = prepare_tool_invocation(
        request=_request(),
        normalizer=_Normalizer(),
        authenticator=_Authenticator(),
        authorizer=_Authorizer(),
        candidate_emitter=_CandidateEmitter(),
        event_recorder=recorder,
        prepared_repository=repo,
        preflight=_Preflight(),
    )

    assert prepared.status is PreparedInvocationStatus.PENDING_APPROVAL
    assert prepared.draft_id == "draft:run-1:req-1"
    assert prepared.governance.candidate_id == "cand-1"
    assert prepared.preflight is not None
    assert prepared.payload.redacted_payload["token"] == "[REDACTED]"
    assert repo.saved == prepared
    assert recorder.events == [
        TOOL_REQUESTED,
        TOOL_VALIDATED,
        TOOL_AUTHN_PASSED,
        TOOL_AUTHZ_PASSED,
        ACTION_CANDIDATE_EMITTED,
        TOOL_PREFLIGHT_COMPUTED,
        TOOL_DRAFT_CREATED,
        TOOL_APPROVAL_PENDING,
    ]


def test_prepare_tool_invocation_fails_closed_on_authz_without_persisting() -> None:
    recorder = _EventRecorder()
    repo = _PreparedRepo()

    with pytest.raises(ToolAuthorizationError, match="denied"):
        prepare_tool_invocation(
            request=_request(),
            normalizer=_Normalizer(),
            authenticator=_Authenticator(),
            authorizer=_Authorizer(fail=True),
            candidate_emitter=_CandidateEmitter(),
            event_recorder=recorder,
            prepared_repository=repo,
            preflight=_Preflight(),
        )

    assert repo.saved is None
    assert ACTION_CANDIDATE_EMITTED not in recorder.events
