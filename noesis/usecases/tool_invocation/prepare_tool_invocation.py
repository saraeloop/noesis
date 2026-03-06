"""Prepare tool invocation intents without crossing the side-effect boundary."""

from __future__ import annotations

from dataclasses import replace

from noesis.domain.tool_contract import EffectKind, PreparedInvocationStatus, PreparedToolInvocation, build_payload_evidence
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
from noesis.domain.tool_contract.reason_codes import GOVERNANCE_APPROVAL_REQUIRED

from .models import ToolInvocationInput
from .ports import (
    PreparedInvocationRepositoryPort,
    ToolAuthenticatorPort,
    ToolAuthorizerPort,
    ToolCandidateEmitterPort,
    ToolEventRecorderPort,
    ToolPayloadNormalizerPort,
    ToolPreflightPort,
)


def prepare_tool_invocation(
    *,
    request: ToolInvocationInput,
    normalizer: ToolPayloadNormalizerPort,
    authenticator: ToolAuthenticatorPort,
    authorizer: ToolAuthorizerPort,
    candidate_emitter: ToolCandidateEmitterPort,
    event_recorder: ToolEventRecorderPort,
    prepared_repository: PreparedInvocationRepositoryPort,
    preflight: ToolPreflightPort | None = None,
) -> PreparedToolInvocation:
    """Validate and persist a prepared tool invocation without executing it."""

    event_recorder.record(
        run_id=request.run_id,
        request_id=request.request_id,
        event_name=TOOL_REQUESTED,
        payload={"protocol": request.protocol.value, "tool": request.tool.name},
    )
    normalized_payload = normalizer.validate_and_normalize(
        protocol=request.protocol,
        tool=request.tool,
        payload=request.raw_payload,
    )
    event_recorder.record(
        run_id=request.run_id,
        request_id=request.request_id,
        event_name=TOOL_VALIDATED,
        payload={"field_count": len(normalized_payload)},
    )

    security = authenticator.authenticate(security=request.security)
    event_recorder.record(
        run_id=request.run_id,
        request_id=request.request_id,
        event_name=TOOL_AUTHN_PASSED,
        payload={"principal_id": security.principal_id},
    )
    authorizer.authorize(request=request, security=security)
    event_recorder.record(
        run_id=request.run_id,
        request_id=request.request_id,
        event_name=TOOL_AUTHZ_PASSED,
        payload={"policy_scope": security.policy_scope},
    )

    candidate_id = candidate_emitter.emit_candidate(
        request=request,
        normalized_payload=normalized_payload,
        candidate_id=request.governance.candidate_id,
    )
    event_recorder.record(
        run_id=request.run_id,
        request_id=request.request_id,
        event_name=ACTION_CANDIDATE_EMITTED,
        payload={"candidate_id": candidate_id},
    )

    payload_evidence = build_payload_evidence(
        normalized_payload,
        policy=request.redaction_policy,
    )
    governance = replace(request.governance, candidate_id=candidate_id)
    status = (
        PreparedInvocationStatus.PENDING_APPROVAL
        if governance.requires_approval
        else PreparedInvocationStatus.PREPARED
    )
    draft_id = request.draft_id or f"draft:{request.run_id}:{request.request_id}"
    prepared = PreparedToolInvocation(
        run_id=request.run_id,
        request_id=request.request_id,
        protocol=request.protocol,
        tool=request.tool,
        payload=payload_evidence,
        execution=request.execution,
        security=security,
        governance=governance,
        status=status,
        draft_id=draft_id,
    )

    if preflight is not None and governance.effect_kind is EffectKind.WRITE:
        binding = preflight.compute(invocation=prepared)
        if binding is not None:
            prepared = replace(prepared, preflight=binding)
            event_recorder.record(
                run_id=request.run_id,
                request_id=request.request_id,
                event_name=TOOL_PREFLIGHT_COMPUTED,
                payload={"impact_hash": binding.impact_hash},
            )

    if governance.effect_kind is EffectKind.WRITE:
        event_recorder.record(
            run_id=request.run_id,
            request_id=request.request_id,
            event_name=TOOL_DRAFT_CREATED,
            payload={"draft_id": draft_id},
        )

    if governance.requires_approval:
        event_recorder.record(
            run_id=request.run_id,
            request_id=request.request_id,
            event_name=TOOL_APPROVAL_PENDING,
            payload={
                "draft_id": draft_id,
                "candidate_id": candidate_id,
                "reason_code": GOVERNANCE_APPROVAL_REQUIRED,
            },
        )

    prepared_repository.save(prepared)
    return prepared


__all__ = ["prepare_tool_invocation"]
