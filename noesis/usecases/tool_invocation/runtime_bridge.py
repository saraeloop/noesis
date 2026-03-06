"""Runtime bridge for approval-gated prepared tool invocation continuation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4

from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.planner.interfaces import ActuationResult, Actuator, EventBus
from noesis.domain.state import NoesisState, PlanStep
from noesis.domain.tool_contract import (
    ApprovalDecisionBindingError,
    ApprovalDecisionRequiredError,
    ExecutionStatus,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    SecurityContext,
    ToolContractError,
    ToolProtocol,
    UnsupportedToolProtocolError,
)
from noesis.runtime.artifacts.ids import action_candidate_uuid
from noesis.runtime.artifacts.manifest import compute_sha256
from noesis.runtime.utils import now
from noesis.trace.events import read_events, write_event
from noesis.usecases.governed_actuation import EpisodeActuationBindings

from .execute_prepared_tool_invocation import execute_prepared_tool_invocation
from .models import ToolInvocationInput
from .ports import (
    ApprovalDecisionRepositoryPort,
    IdempotencyStorePort,
    PreparedInvocationRepositoryPort,
    ToolAuthenticatorPort,
    ToolAuthorizerPort,
    ToolCandidateEmitterPort,
    ToolDispatchPort,
    ToolEventRecorderPort,
    ToolPayloadNormalizerPort,
    ToolPreflightPort,
)
from .prepare_tool_invocation import prepare_tool_invocation


@dataclass(frozen=True, slots=True)
class ToolRuntimeBridgePorts:
    """Dependencies needed to bridge prepared tool contracts into runtime continuation."""

    prepared_repository: PreparedInvocationRepositoryPort
    approval_repository: ApprovalDecisionRepositoryPort
    idempotency_store: IdempotencyStorePort
    dispatch: ToolDispatchPort
    normalizer: ToolPayloadNormalizerPort | None = None
    authenticator: ToolAuthenticatorPort | None = None
    authorizer: ToolAuthorizerPort | None = None
    preflight: ToolPreflightPort | None = None


@dataclass(slots=True)
class ToolContractContinuationActuator(Actuator):
    """Actuator that pauses for approval, then resumes by durable draft identity."""

    request_factory: Callable[[str], ToolInvocationInput] | None
    ports: ToolRuntimeBridgePorts
    run_dir: Path
    now_fn: Callable[[], str]
    id_factory: Callable[[], UUID]
    run_lifecycle: Any | None = None
    result: Any | None = None
    error: Exception | None = None
    dispatched_draft_id: str | None = None
    prepared_draft_id: str | None = None
    pause_required: bool = False
    pause_cause_event_id: str | None = None

    def execute(
        self,
        *,
        plan: list[PlanStep] | tuple[PlanStep, ...],
        request: Any,
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        run_id = request.context.episode_id
        if self.request_factory is None:
            return self._resume_prepared(run_id=run_id, request=request, state=state)
        return self._prepare_then_continue(run_id=run_id, request=request, state=state, event_bus=event_bus)

    def _prepare_then_continue(
        self,
        *,
        run_id: str,
        request: Any,
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        if self.ports.normalizer is None or self.ports.authenticator is None or self.ports.authorizer is None:
            raise ValueError("tool runtime preparation requires normalizer, authenticator, and authorizer")
        tool_request = self.request_factory(run_id)  # type: ignore[misc]
        _require_supported_runtime_protocol(tool_request.protocol, operation="prepare")
        recorder = RuntimeToolEventRecorder(
            run_id=run_id,
            run_dir=self.run_dir,
            now_fn=self.now_fn,
            id_factory=self.id_factory,
        )
        candidate_emitter = RuntimeToolCandidateEmitter(
            run_id=run_id,
            run_dir=self.run_dir,
            event_bus=event_bus,
            state_hash_resolver=lambda: _state_hash(self.run_dir),
            event_recorder=recorder,
        )
        prepared = prepare_tool_invocation(
            request=tool_request,
            normalizer=self.ports.normalizer,
            authenticator=self.ports.authenticator,
            authorizer=self.ports.authorizer,
            candidate_emitter=candidate_emitter,
            event_recorder=recorder,
            prepared_repository=self.ports.prepared_repository,
            preflight=self.ports.preflight,
        )
        self.prepared_draft_id = prepared.draft_id
        if prepared.status is PreparedInvocationStatus.PENDING_APPROVAL:
            self.pause_required = True
            self.pause_cause_event_id = _latest_event_id(self.run_dir)
            return ActuationResult(
                status="interrupted",
                summary=f"Approval required for tool draft {prepared.draft_id}",
                metrics={},
                reasons=[f"draft:{prepared.draft_id}"],
                success=False,
            )
        self.ports.prepared_repository.save(replace(prepared, status=PreparedInvocationStatus.APPROVED))
        return self._execute_prepared(
            prepared=prepared,
            request=request,
            state=state,
            initial_cause=None,
        )

    def _resume_prepared(
        self,
        *,
        run_id: str,
        request: Any,
        state: NoesisState,
    ) -> ActuationResult:
        prepared = self.ports.prepared_repository.load_pending_for_run(run_id=run_id)
        if prepared is None or not prepared.draft_id:
            return _error_result("No pending prepared tool invocation exists for resume", "pending_draft_not_found")
        return self._execute_prepared(
            prepared=prepared,
            request=request,
            state=state,
            initial_cause=_latest_event_id(self.run_dir),
        )

    def _execute_prepared(
        self,
        *,
        prepared: PreparedToolInvocation,
        request: Any,
        state: NoesisState,
        initial_cause: str | None,
    ) -> ActuationResult:
        recorder = RuntimeToolEventRecorder(
            run_id=prepared.run_id,
            run_dir=self.run_dir,
            initial_cause=initial_cause,
            now_fn=self.now_fn,
            id_factory=self.id_factory,
        )
        try:
            result = execute_prepared_tool_invocation(
                run_id=prepared.run_id,
                draft_id=prepared.draft_id or "",
                prepared_repository=self.ports.prepared_repository,
                approval_repository=self.ports.approval_repository,
                idempotency_store=self.ports.idempotency_store,
                dispatch=self.ports.dispatch,
                event_recorder=recorder,
            )
        except (ApprovalDecisionRequiredError, ApprovalDecisionBindingError) as exc:
            self.error = exc
            self.ports.prepared_repository.save(replace(prepared, status=PreparedInvocationStatus.PENDING_APPROVAL))
            self.pause_required = True
            self.pause_cause_event_id = _latest_event_id(self.run_dir)
            return ActuationResult(
                status="interrupted",
                summary=str(exc),
                metrics={},
                reasons=[exc.__class__.__name__],
                success=False,
            )
        except ToolContractError as exc:
            self.error = exc
            return _error_result(str(exc), exc.__class__.__name__)

        self.result = result
        self.dispatched_draft_id = prepared.draft_id
        self.ports.prepared_repository.save(replace(prepared, status=PreparedInvocationStatus.APPROVED))
        step_id = state.plan_steps[-1].id if state.plan_steps else None
        state.record_action(
            kind=prepared.protocol.value,
            tool=_tool_label(prepared),
            input_excerpt=_tool_input_excerpt(prepared),
            result_status=result.status.value,
            step_id=step_id,
            extensions={"x-tool_draft_id": prepared.draft_id} if prepared.draft_id else None,
        )
        if result.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.REPLAYED}:
            return ActuationResult(
                status="ok",
                summary=_success_summary(result),
                metrics={"success": 1.0},
                reasons=[result.reason_code] if result.reason_code else [],
                success=True,
            )
        return ActuationResult(
            status="error",
            summary=result.reason_code or "tool execution failed",
            metrics={"success": 0.0},
            reasons=[result.reason_code] if result.reason_code else [],
            success=False,
        )


@dataclass(slots=True)
class RuntimeToolEventRecorder(ToolEventRecorderPort):
    """Append tool-contract events into the canonical run event history."""

    run_id: str
    run_dir: Path
    initial_cause: str | None = None
    now_fn: Callable[[], str] = now
    id_factory: Callable[[], UUID] = uuid4
    _last_emitted_id: str | None = None

    def seed(self, *, caused_by: str | None) -> None:
        self.initial_cause = None
        self._last_emitted_id = caused_by

    def record(
        self,
        *,
        run_id: str,
        request_id: str,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        event_id = str(self.id_factory())
        caused_by = self._last_emitted_id or self.initial_cause or _latest_event_id(self.run_dir)
        record: dict[str, Any] = {
            "id": event_id,
            "timestamp": self.now_fn(),
            "episode_id": run_id,
            "agent_id": "tool_contract",
            "phase": "tool",
            "payload": {"event_name": event_name, "request_id": request_id, **dict(payload)},
            "evidence_ids": [],
        }
        if caused_by:
            record["caused_by"] = caused_by
        write_event(self.run_dir, record)
        self._last_emitted_id = event_id


@dataclass(slots=True)
class RuntimeToolCandidateEmitter(ToolCandidateEmitterPort):
    """Emit canonical action-candidate evidence for tool-contract requests."""

    run_id: str
    run_dir: Path
    event_bus: EventBus
    state_hash_resolver: Callable[[], str]
    event_recorder: RuntimeToolEventRecorder

    def emit_candidate(
        self,
        *,
        request: ToolInvocationInput,
        normalized_payload: Mapping[str, Any],
        candidate_id: str | None,
    ) -> str:
        candidate = ActionCandidate(
            id=candidate_id,
            kind=f"tool.{request.tool.namespace}.{request.tool.name}",
            payload=dict(normalized_payload),
            state_ref="state.json",
            state_hash=self.state_hash_resolver(),
            redaction=_candidate_redaction(request),
            provenance={
                "request_id": request.request_id,
                **({"draft_id": request.draft_id} if request.draft_id else {}),
                "protocol": request.protocol.value,
            },
            risk_tags=tuple(request.governance.tags),
        )
        if not candidate.id:
            candidate = candidate.with_id(str(action_candidate_uuid(self.run_id, candidate.canonical_json())))
        candidate_event_id = self.event_bus.emit_action_candidate(
            candidate=candidate,
            caused_by=_latest_event_uuid(self.run_dir),
        )
        self.event_recorder.seed(caused_by=str(candidate_event_id))
        return candidate.id


@dataclass(slots=True)
class PassthroughAuthenticator(ToolAuthenticatorPort):
    def authenticate(self, *, security: SecurityContext) -> SecurityContext:
        return security


@dataclass(slots=True)
class AllowAllAuthorizer(ToolAuthorizerPort):
    def authorize(self, *, request: ToolInvocationInput, security: SecurityContext) -> None:
        return None


def build_tool_invocation_actuation_bindings(
    *,
    request_factory: Callable[[str], ToolInvocationInput],
    run_dir: Path,
    ports: ToolRuntimeBridgePorts,
    run_lifecycle: Any,
    now_fn: Callable[[], str] = now,
    id_factory: Callable[[], UUID] = uuid4,
    ) -> EpisodeActuationBindings:
    """Build bindings that prepare a tool draft and pause on approval before side effects."""

    return EpisodeActuationBindings(
        actuator=ToolContractContinuationActuator(
            request_factory=request_factory,
            ports=ports,
            run_dir=run_dir,
            now_fn=now_fn,
            id_factory=id_factory,
            run_lifecycle=run_lifecycle,
        )
    )


def build_resumed_tool_invocation_actuation_bindings(
    *,
    run_dir: Path,
    ports: ToolRuntimeBridgePorts,
    now_fn: Callable[[], str] = now,
    id_factory: Callable[[], UUID] = uuid4,
) -> EpisodeActuationBindings:
    """Build bindings that resume and execute one already-prepared pending draft."""

    return EpisodeActuationBindings(
        actuator=ToolContractContinuationActuator(
            request_factory=None,
            ports=ports,
            run_dir=run_dir,
            now_fn=now_fn,
            id_factory=id_factory,
        )
    )


def _candidate_redaction(request: ToolInvocationInput) -> RedactionSpec:
    policy = request.redaction_policy
    field_rules: dict[str, str] = {}
    if policy is not None:
        field_rules.update({field: "redact" for field in policy.redact_fields})
        field_rules.update({field: "hash" for field in policy.hash_fields})
    return RedactionSpec(
        mode="field_policy" if field_rules else "none",
        policy_id="tool.redaction",
        policy_version="1.0.0",
        field_rules=field_rules,
    )


def _tool_input_excerpt(invocation: PreparedToolInvocation) -> str:
    payload = invocation.payload.redacted_payload
    for key in ("command", "argv", "path", "url"):
        if key in payload:
            return str(payload[key])[:120]
    return f"{invocation.tool.namespace}.{invocation.tool.name}"[:120]


def _tool_label(invocation: PreparedToolInvocation) -> str:
    version = f":{invocation.tool.version}" if invocation.tool.version else ""
    return f"{invocation.tool.namespace}.{invocation.tool.name}{version}"


def _success_summary(result: Any) -> str:
    if result.status is ExecutionStatus.REPLAYED:
        return result.reason_code or "tool execution replayed"
    return result.reason_code or "tool execution succeeded"


def _error_result(summary: str, reason: str) -> ActuationResult:
    return ActuationResult(
        status="error",
        summary=summary,
        metrics={"success": 0.0},
        reasons=[reason],
        success=False,
    )


def _state_hash(run_dir: Path) -> str:
    state_path = run_dir / "state.json"
    if state_path.exists():
        return compute_sha256(state_path)
    return f"sha256:{'0' * 64}"


def _latest_event_id(run_dir: Path) -> str | None:
    events = read_events(run_dir)
    if not events:
        return None
    event_id = events[-1].get("id")
    return event_id if isinstance(event_id, str) else None


def _latest_event_uuid(run_dir: Path) -> UUID | None:
    event_id = _latest_event_id(run_dir)
    if event_id is None:
        return None
    try:
        return UUID(event_id)
    except ValueError:
        return None


def _require_supported_runtime_protocol(protocol: ToolProtocol, *, operation: str) -> None:
    if protocol is ToolProtocol.SUBPROCESS:
        return
    raise UnsupportedToolProtocolError(
        f"tool runtime bridge only supports subprocess during ADR-016 PR-4; "
        f"cannot {operation} protocol={protocol.value!r}"
    )


__all__ = [
    "AllowAllAuthorizer",
    "PassthroughAuthenticator",
    "RuntimeToolCandidateEmitter",
    "RuntimeToolEventRecorder",
    "ToolContractContinuationActuator",
    "ToolRuntimeBridgePorts",
    "build_resumed_tool_invocation_actuation_bindings",
    "build_tool_invocation_actuation_bindings",
]
