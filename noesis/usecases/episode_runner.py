"""
Episode runner use case.

Coordinates planner and actuator dependencies to execute a cognitive episode
while keeping orchestration logic free from infrastructure concerns.
"""

from __future__ import annotations

import re
import inspect
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from noesis.domain.planner.interfaces import (
    Actuator,
    ActuationResult,
    EventBus,
    Planner,
)
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.faculties.direction import PlannerDirective, DirectiveStatus
from noesis.domain.faculties.governance import (
    GovernanceDecision,
    GovernanceFailurePolicy,
    GovernanceMode,
    GovernanceResult,
    PreActGovernor,
    with_governance_context,
)
from noesis.domain.faculties.intuition import Intuition, IntuitionEvent
from noesis.domain.state import CognitiveEvent, CognitiveMetrics, CognitiveVerb, LineageTracker, NoesisState, PlanKind, PlanStep, OUTCOME_STATUS_VETOED
from noesis import events as runtime_events
from noesis.trace.events import is_terminate_event
from noesis.infrastructure.state_repository import EpisodeContext
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.runtime.artifacts.ids import directive_uuid, governance_uuid
from noesis.trace.events import read_events
from noesis.runtime.normalization import normalize_using
from noesis.usecases.actuation.candidate_builder import DefaultActionCandidateBuilder
from noesis.usecases.actuation.governed_actuator import ActionCandidateBuilder, GovernedActuator
from .hooks.meta_phase import CompositeMetaPhaseHook, MetaPhaseHook, NullMetaPhaseHook
from .ports import (
    ClockPort,
    EventHistoryPort,
    EventIdFactoryPort,
    EventSinkPort,
    PromptRecorderPort,
    StateRepositoryPort,
)


class _EventHistoryAdapter:
    """Structural adapter to expose read_events as a port."""

    def read(self, run_dir) -> Sequence[Dict[str, object]]:
        return read_events(run_dir)


@dataclass(slots=True)
class EpisodeRequest:
    goal: str
    beliefs: tuple[str, ...]
    context: EpisodeContext
    using_label: str | None = None

    @property
    def episode_id(self) -> str:
        return self.context.episode_id

    @property
    def seed(self) -> int:
        return self.context.seed

    @property
    def adapter_label(self) -> str:
        return self.context.adapter_label


@dataclass(slots=True)
class EpisodeOutcome:
    status: str
    success: bool
    summary: str | None
    metrics: dict[str, float]
    reasons: list[str]


@dataclass(slots=True)
class EpisodeResult:
    state: NoesisState
    outcome: EpisodeOutcome
    plan: Sequence[PlanStep]


@dataclass(slots=True)
class EpisodeDependencies:
    planner: Planner
    actuator: Actuator
    event_bus: EventBus
    state_repository: StateRepositoryPort
    direction_planner: MetaPlanner | None = None
    governance_policy: PreActGovernor | None = None
    governance_mode: GovernanceMode = GovernanceMode.OFF
    governance_failure_policy: GovernanceFailurePolicy | None = None
    governance_timeout_ms: int | None = None
    intuition_policy: Intuition | None = None
    intuition_enabled: bool = False
    action_candidate_builder: ActionCandidateBuilder | None = None


@dataclass(slots=True)
class EpisodeInstrumentation:
    clock: ClockPort
    emitter: EventSinkPort
    lineage: LineageTracker
    event_history: EventHistoryPort = field(default_factory=_EventHistoryAdapter)
    prompt_recorder: PromptRecorderPort | None = None
    now: Callable[[], datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id_factory: EventIdFactoryPort | Callable[[], UUID] = uuid4
    rng: object | None = None
    hooks: Sequence[MetaPhaseHook] = field(default_factory=lambda: (NullMetaPhaseHook(),))


class EpisodeRunner:
    """Application service orchestrating an episode via dependency injection."""

    def __init__(
        self,
        deps: EpisodeDependencies,
        *,
        instrumentation: EpisodeInstrumentation | None = None,
    ) -> None:
        self._deps = self._wrap_actuator(deps)
        context = getattr(deps.state_repository, "context", None)
        if instrumentation is None:
            if context is None:
                raise ValueError("EpisodeRunner requires instrumentation or a repository context")
            instrumentation = EpisodeInstrumentation(
                clock=RuntimeClock(),
                emitter=CognitiveEventEmitter(run_dir=context.run_dir),
                lineage=LineageTracker(),
                event_history=_EventHistoryAdapter(),
                prompt_recorder=getattr(context, "prompt_recorder", None),
                now=datetime.now,
                event_id_factory=uuid4,
                hooks=(NullMetaPhaseHook(),),
            )
        self._clock = instrumentation.clock
        self._emitter = instrumentation.emitter
        self._lineage = instrumentation.lineage
        self._event_history = instrumentation.event_history
        self._now = instrumentation.now
        factory = instrumentation.event_id_factory
        self._event_id_factory = factory if callable(factory) else (lambda: factory)
        hooks = instrumentation.hooks or (NullMetaPhaseHook(),)
        self._hooks = CompositeMetaPhaseHook(tuple(hooks))
        self._context = context
        self._prompt_recorder: PromptRecorderPort | None = instrumentation.prompt_recorder or getattr(context, "prompt_recorder", None)

    def _wrap_actuator(self, deps: EpisodeDependencies) -> EpisodeDependencies:
        if deps.governance_policy is None:
            return deps
        if deps.governance_mode is GovernanceMode.OFF:
            return deps
        if isinstance(deps.actuator, GovernedActuator):
            return deps
        builder = deps.action_candidate_builder or DefaultActionCandidateBuilder()
        governed = GovernedActuator(
            inner=deps.actuator,
            candidate_builder=builder,
            governance_policy=deps.governance_policy,
            governance_mode=deps.governance_mode,
            failure_policy=deps.governance_failure_policy,
            timeout_ms=deps.governance_timeout_ms,
        )
        return replace(deps, actuator=governed)

    def run(self, request: EpisodeRequest) -> EpisodeResult:
        context = request.context
        self._seed_lineage(context)
        state = self._deps.state_repository.init(request.context)

        observe_event = self._run_observe(request, state)
        intuition_signals, intuition_event_id = self._run_intuition(request, state, observe_event.event_id)
        signals = tuple(request.beliefs) + tuple(intuition_signals)
        interpret_event = self._run_interpret(request, signals, caused_by=intuition_event_id)
        plan, plan_event, direction_event_id = self._run_plan(request, state, signals)
        actuation, act_event = self._run_act(plan, plan_event, direction_event_id, request, state)
        if act_event is None:
            state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
            state.set_outcome(status=actuation.status, summary=actuation.summary, metrics=actuation.metrics)
            self._deps.state_repository.persist(state)
            self._maybe_emit_terminate(
                context,
                {"status": actuation.status, "message": actuation.summary},
            )
            outcome = EpisodeOutcome(
                status=actuation.status,
                success=actuation.success,
                summary=actuation.summary,
                metrics=actuation.metrics,
                reasons=actuation.reasons,
            )
            return EpisodeResult(state=state, outcome=outcome, plan=plan)

        reflect_event = self._run_reflect(actuation, plan_event.event_id)
        self._run_learn(actuation, reflect_event.event_id)

        state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
        state.set_outcome(status=actuation.status, summary=actuation.summary, metrics=actuation.metrics)
        self._deps.state_repository.persist(state)
        self._maybe_emit_terminate(
            context,
            {"status": actuation.status, "message": actuation.summary},
        )

        outcome = EpisodeOutcome(
            status=actuation.status,
            success=actuation.success,
            summary=actuation.summary,
            metrics=actuation.metrics,
            reasons=actuation.reasons,
        )
        return EpisodeResult(state=state, outcome=outcome, plan=plan)

    async def run_async(self, request: EpisodeRequest) -> EpisodeResult:
        context = request.context
        self._seed_lineage(context)
        state = self._deps.state_repository.init(request.context)

        observe_event = self._run_observe(request, state)
        intuition_signals, intuition_event_id = self._run_intuition(request, state, observe_event.event_id)
        signals = tuple(request.beliefs) + tuple(intuition_signals)
        interpret_event = self._run_interpret(request, signals, caused_by=intuition_event_id)
        plan, plan_event, direction_event_id = self._run_plan(request, state, signals)
        actuation, act_event = await self._run_act_async(
            plan,
            plan_event,
            direction_event_id,
            request,
            state,
        )
        if act_event is None:
            state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
            state.set_outcome(status=actuation.status, summary=actuation.summary, metrics=actuation.metrics)
            self._deps.state_repository.persist(state)
            self._maybe_emit_terminate(
                context,
                {"status": actuation.status, "message": actuation.summary},
            )
            outcome = EpisodeOutcome(
                status=actuation.status,
                success=actuation.success,
                summary=actuation.summary,
                metrics=actuation.metrics,
                reasons=actuation.reasons,
            )
            return EpisodeResult(state=state, outcome=outcome, plan=plan)

        reflect_event = self._run_reflect(actuation, plan_event.event_id)
        self._run_learn(actuation, reflect_event.event_id)

        state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
        state.set_outcome(status=actuation.status, summary=actuation.summary, metrics=actuation.metrics)
        self._deps.state_repository.persist(state)
        self._maybe_emit_terminate(
            context,
            {"status": actuation.status, "message": actuation.summary},
        )

        outcome = EpisodeOutcome(
            status=actuation.status,
            success=actuation.success,
            summary=actuation.summary,
            metrics=actuation.metrics,
            reasons=actuation.reasons,
        )
        return EpisodeResult(state=state, outcome=outcome, plan=plan)

    def _run_observe(self, request: EpisodeRequest, state: NoesisState) -> CognitiveEvent:
        verb = CognitiveVerb.OBSERVE
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        metrics = self._clock.stop(token)
        snapshot = self._build_snapshot(request, state)
        observed_at = metrics.started_at.isoformat() if metrics else self._now().isoformat()
        payload: Dict[str, object] = {
            "task": request.goal,
            "tags": context.tags,
            "timestamp": observed_at,
            "experimental": {"snapshot": snapshot},
        }
        event = self._emit_event(verb=verb, context=context, payload=payload, metrics=metrics)
        self._hooks.after_phase(verb, context, event)
        return event

    def _run_intuition(
        self,
        request: EpisodeRequest,
        state: NoesisState,
        caused_by: UUID | None,
    ) -> tuple[list[str], UUID | None]:
        if not self._deps.intuition_enabled or self._deps.intuition_policy is None:
            return [], None

        snapshot = self._build_snapshot(request, state)
        result: IntuitionEvent | None = self._deps.intuition_policy.advise(snapshot)
        if result is None:
            return [], None

        event_id = self._event_id_factory()
        timestamp = self._now().isoformat()
        record: Dict[str, object] = {
            "id": str(event_id),
            "timestamp": timestamp,
            "episode_id": request.context.episode_id,
            "agent_id": "intuition",
            "phase": "intuition",
            "payload": result.to_dict(),
            "evidence_ids": [],
        }
        if caused_by is not None:
            record["caused_by"] = str(caused_by)
        from noesis.trace.events import write_event

        write_event(request.context.run_dir, record)

        recorder = self._resolve_prompt_recorder(request.context)
        if recorder:
            rendered = f"[intuition] goal={request.goal or 'unspecified'} | kind={result.kind}"
            self._record_prompt(
                recorder=recorder,
                phase="intuition",
                agent_id="intuition",
                rendered=rendered,
                role="system",
                kind="intuition",
                template_id="intuition.v1",
                tags=request.context.tags,
                event_id=event_id,
            )

        signals = [f"directive:{result.kind}", result.advice]
        return signals, event_id

    def _maybe_emit_terminate(self, context: EpisodeContext, payload: Dict[str, object]) -> None:
        """Emit terminate once if not already recorded."""
        events = self._event_history.read(context.run_dir)
        if any(is_terminate_event(evt) for evt in events):
            return
        status_value = str(payload.get("status", "unknown") or "unknown")
        default_message = "Episode terminated."
        message_raw = payload.get("message")
        message_value = str(message_raw).strip() if message_raw else ""
        if not message_value:
            message_value = (
                f"{status_value}." if status_value and status_value != "unknown" else default_message
            )
        terminate_payload = dict(payload)
        terminate_payload["status"] = status_value
        terminate_payload["message"] = message_value
        now_fn = None
        if hasattr(self._clock, "now"):
            def _deterministic_now() -> str:
                ts = self._clock.now()
                return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            now_fn = _deterministic_now
        runtime_events.terminate(
            context.run_dir,
            context.episode_id,
            terminate_payload,
            now_fn=now_fn,
            id_factory=self._event_id_factory,
        )

    def _seed_lineage(self, context: EpisodeContext) -> None:
        events = self._event_history.read(context.run_dir)
        last_id: UUID | None = None
        for event in reversed(events):
            raw_id = event.get("id")
            if isinstance(raw_id, str):
                try:
                    last_id = UUID(raw_id)
                    break
                except ValueError:
                    continue
        self._lineage.seed(last_event_id=last_id)

    def _emit_event(
        self,
        *,
        verb: CognitiveVerb,
        context: EpisodeContext,
        payload: Dict[str, object],
        metrics: CognitiveMetrics,
        agent_id: str = "system",
        cause: UUID | None = None,
    ) -> CognitiveEvent:
        event_id = self._event_id_factory()
        event = CognitiveEvent(
            episode_id=context.episode_id,
            verb=verb,
            payload=payload,
            timestamp=metrics.completed_at or self._now(),
            event_id=event_id,
        ).with_metrics(metrics)
        linked = self._lineage.register(event, cause=cause)
        self._emitter.emit(linked, agent_id=agent_id)
        self._hooks.after_phase(verb, context, linked)
        return linked

    def _run_interpret(
        self,
        request: EpisodeRequest,
        signals: Sequence[str],
        *,
        caused_by: UUID | None = None,
    ) -> CognitiveEvent:
        verb = CognitiveVerb.INTERPRET
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        metrics = self._clock.stop(token)
        payload: Dict[str, object] = {"signals": list(signals)}
        event = self._emit_event(verb=verb, context=context, payload=payload, metrics=metrics, cause=caused_by)

        recorder = self._resolve_prompt_recorder(context)
        if recorder:
            rendered = f"[interpret] goal={request.goal or 'unspecified'} | signals={len(signals)}"
            self._record_prompt(
                recorder=recorder,
                phase="interpret",
                agent_id="interpret",
                rendered=rendered,
                role="system",
                kind="reasoning",
                template_id="interpret.v1",
                tags=context.tags,
                event_id=event.event_id,
            )

        return event

    def _run_plan(
        self,
        request: EpisodeRequest,
        state: NoesisState,
        beliefs: Sequence[str],
    ) -> tuple[list[PlanStep], CognitiveEvent, Optional[UUID]]:
        verb = CognitiveVerb.PLAN
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan = self._deps.planner.build_plan(goal=request.goal, beliefs=beliefs)
        directive: PlannerDirective | None = None
        if self._deps.direction_planner is not None:
            proposed = self._deps.direction_planner.propose(
                goal=request.goal,
                beliefs=beliefs,
                base_plan=plan,
            )
            if proposed is not None:
                directive = _with_stable_directive_id(proposed, context.episode_id)
                if directive.applied:
                    _apply_directive(plan, directive)
        metrics = self._clock.stop(token)
        rationale = "minimal planner"
        if directive and directive.applied:
            rationale = f"{rationale} + meta"
        state.set_plan(steps=plan, rationale=rationale, source="planner.minimal")
        plan_event = self._deps.event_bus.emit_plan(
            steps=plan,
            rationale=rationale,
            source="planner.minimal",
            metrics=metrics,
            caused_by=None,
        )
        self._record_plan_prompt(request, plan)
        self._hooks.after_phase(verb, context, plan_event)
        plan_anchor = plan_event.event_id
        direction_event_id: Optional[UUID] = None
        if directive is not None and directive.status is not DirectiveStatus.SKIPPED:
            direction_event_id = self._deps.event_bus.emit_direction(
                directive=directive,
                caused_by=plan_anchor,
            )
        return plan, plan_event, direction_event_id

    def _run_act(
        self,
        plan: Sequence[PlanStep],
        plan_event: CognitiveEvent,
        direction_event_id: Optional[UUID],
        request: EpisodeRequest,
        state: NoesisState,
    ) -> tuple[ActuationResult, CognitiveEvent | None]:
        verb = CognitiveVerb.ACT
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan_anchor = plan_event.event_id
        latest_direction_id: Optional[UUID] = direction_event_id
        governance_result: GovernanceResult | None = None
        governance_event_id: Optional[UUID] = None
        mode = _parse_governance_mode(getattr(self._deps, "governance_mode", GovernanceMode.OFF))
        failure_policy = _parse_failure_policy(
            getattr(self._deps, "governance_failure_policy", None),
            mode,
        )
        if self._deps.governance_policy is not None and mode is not GovernanceMode.OFF:
            governance_error: Dict[str, object] | None = None
            try:
                raw_result = _evaluate_governance(
                    policy=self._deps.governance_policy,
                    goal=request.goal,
                    plan=plan,
                    timeout_ms=getattr(self._deps, "governance_timeout_ms", None),
                )
            except Exception as exc:  # noqa: BLE001
                governance_error = _governance_error_payload(exc)
                raw_result = GovernanceResult(
                    decision=GovernanceDecision.AUDIT,
                    rule_id="rule:governance.failure",
                    score=0.0,
                    message="Governance evaluation failed",
                    policy_id="policy:runtime.governance",
                    policy_version="1.0.0",
                    policy_kind="rules",
                    details={"error": governance_error},
                )
            governance_result = with_governance_context(
                _with_stable_governance_id(raw_result, context.episode_id),
                mode=mode,
                failure_policy=failure_policy,
                enforced=(
                    mode is GovernanceMode.ENFORCE
                    and raw_result.decision is GovernanceDecision.VETO
                    and governance_error is None
                ),
                error=governance_error,
            )
            blocked_direction_id: Optional[UUID] = None
            if (
                governance_result.decision is GovernanceDecision.VETO
                and mode is GovernanceMode.ENFORCE
                and governance_error is None
            ):
                blocked_direction_id = _emit_governance_blocked_direction(
                    event_bus=self._deps.event_bus,
                    plan=plan,
                    governance_result=governance_result,
                    caused_by=latest_direction_id or plan_anchor,
                )
                latest_direction_id = blocked_direction_id
            governance_event_id = self._deps.event_bus.emit_governance(
                result=governance_result,
                caused_by=blocked_direction_id or latest_direction_id or plan_anchor,
            )
            recorder = self._resolve_prompt_recorder(request.context)
            if recorder:
                rendered_governance = (
                    f"[governance] policy={governance_result.policy_id} decision={governance_result.decision.value}"
                )
                self._record_prompt(
                    recorder=recorder,
                    phase="governance",
                    agent_id="governance",
                    rendered=rendered_governance,
                    role="system",
                    kind="governance",
                    template_id="governance.v1",
                    tags=request.context.tags,
                    event_id=governance_event_id,
                )
            if governance_error and mode is GovernanceMode.ENFORCE and failure_policy is GovernanceFailurePolicy.FAIL_CLOSED:
                _ = self._clock.stop(token)
                return (
                    ActuationResult(
                        status="error",
                        summary=governance_result.message or "Governance evaluation failed",
                        metrics={},
                        reasons=["governance_failure"],
                        success=False,
                    ),
                    None,
                )
            if governance_result.decision is GovernanceDecision.VETO and mode is GovernanceMode.ENFORCE:
                _ = self._clock.stop(token)
                return (
                    ActuationResult(
                        status=OUTCOME_STATUS_VETOED,
                        summary=governance_result.message or "Episode vetoed by governance",
                        metrics={},
                        reasons=[governance_result.rule_id],
                        success=False,
                    ),
                    None,
                )
        actuation = self._deps.actuator.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=self._deps.event_bus,
        )
        if actuation.status == "vetoed" or (
            actuation.status == "error" and "governance_failure" in actuation.reasons
        ):
            _ = self._clock.stop(token)
            return actuation, None
        if governance_result and (
            governance_result.decision is GovernanceDecision.AUDIT
            or (governance_result.decision is GovernanceDecision.VETO and mode is GovernanceMode.AUDIT)
        ):
            actuation.reasons.append(governance_result.rule_id)
        metrics = self._clock.stop(token)
        excerpt_basis = plan[0].description if plan else request.goal
        payload: Dict[str, object] = {
            "input_excerpt": excerpt_basis or "",
            "outcome": actuation.status,
            "adapter": request.context.adapter_label,
            "reasons": actuation.reasons,
            "synthetic": True,
        }
        event = self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            agent_id=request.context.adapter_label,
            cause=latest_direction_id or governance_event_id or plan_anchor,
        )
        return actuation, event

    async def _await_actuation(self, value: ActuationResult | object) -> ActuationResult:
        if inspect.isawaitable(value):
            return await value  # type: ignore[return-value]
        return value  # type: ignore[return-value]

    async def _run_act_async(
        self,
        plan: Sequence[PlanStep],
        plan_event: CognitiveEvent,
        direction_event_id: Optional[UUID],
        request: EpisodeRequest,
        state: NoesisState,
    ) -> tuple[ActuationResult, CognitiveEvent | None]:
        verb = CognitiveVerb.ACT
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan_anchor = plan_event.event_id
        latest_direction_id: Optional[UUID] = direction_event_id
        governance_result: GovernanceResult | None = None
        governance_event_id: Optional[UUID] = None
        mode = _parse_governance_mode(getattr(self._deps, "governance_mode", GovernanceMode.OFF))
        failure_policy = _parse_failure_policy(
            getattr(self._deps, "governance_failure_policy", None),
            mode,
        )
        if self._deps.governance_policy is not None and mode is not GovernanceMode.OFF:
            governance_error: Dict[str, object] | None = None
            try:
                raw_result = _evaluate_governance(
                    policy=self._deps.governance_policy,
                    goal=request.goal,
                    plan=plan,
                    timeout_ms=getattr(self._deps, "governance_timeout_ms", None),
                )
            except Exception as exc:  # noqa: BLE001
                governance_error = _governance_error_payload(exc)
                raw_result = GovernanceResult(
                    decision=GovernanceDecision.AUDIT,
                    rule_id="rule:governance.failure",
                    score=0.0,
                    message="Governance evaluation failed",
                    policy_id="policy:runtime.governance",
                    policy_version="1.0.0",
                    policy_kind="rules",
                    details={"error": governance_error},
                )
            governance_result = with_governance_context(
                _with_stable_governance_id(raw_result, context.episode_id),
                mode=mode,
                failure_policy=failure_policy,
                enforced=(
                    mode is GovernanceMode.ENFORCE
                    and raw_result.decision is GovernanceDecision.VETO
                    and governance_error is None
                ),
                error=governance_error,
            )
            blocked_direction_id: Optional[UUID] = None
            if (
                governance_result.decision is GovernanceDecision.VETO
                and mode is GovernanceMode.ENFORCE
                and governance_error is None
            ):
                blocked_direction_id = _emit_governance_blocked_direction(
                    event_bus=self._deps.event_bus,
                    plan=plan,
                    governance_result=governance_result,
                    caused_by=latest_direction_id or plan_anchor,
                )
                latest_direction_id = blocked_direction_id
            governance_event_id = self._deps.event_bus.emit_governance(
                result=governance_result,
                caused_by=blocked_direction_id or latest_direction_id or plan_anchor,
            )
            recorder = self._resolve_prompt_recorder(request.context)
            if recorder:
                rendered_governance = (
                    f"[governance] policy={governance_result.policy_id} decision={governance_result.decision.value}"
                )
                self._record_prompt(
                    recorder=recorder,
                    phase="governance",
                    agent_id="governance",
                    rendered=rendered_governance,
                    role="system",
                    kind="governance",
                    template_id="governance.v1",
                    tags=request.context.tags,
                    event_id=governance_event_id,
                )
            if governance_error and mode is GovernanceMode.ENFORCE and failure_policy is GovernanceFailurePolicy.FAIL_CLOSED:
                _ = self._clock.stop(token)
                return (
                    ActuationResult(
                        status="error",
                        summary=governance_result.message or "Governance evaluation failed",
                        metrics={},
                        reasons=["governance_failure"],
                        success=False,
                    ),
                    None,
                )
            if governance_result.decision is GovernanceDecision.VETO and mode is GovernanceMode.ENFORCE:
                _ = self._clock.stop(token)
                return (
                    ActuationResult(
                        status=OUTCOME_STATUS_VETOED,
                        summary=governance_result.message or "Episode vetoed by governance",
                        metrics={},
                        reasons=[governance_result.rule_id],
                        success=False,
                    ),
                    None,
                )
        actuation_value = self._deps.actuator.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=self._deps.event_bus,
        )
        actuation = await self._await_actuation(actuation_value)
        if actuation.status == "vetoed" or (
            actuation.status == "error" and "governance_failure" in actuation.reasons
        ):
            _ = self._clock.stop(token)
            return actuation, None
        if governance_result and (
            governance_result.decision is GovernanceDecision.AUDIT
            or (governance_result.decision is GovernanceDecision.VETO and mode is GovernanceMode.AUDIT)
        ):
            actuation.reasons.append(governance_result.rule_id)
        metrics = self._clock.stop(token)
        excerpt_basis = plan[0].description if plan else request.goal
        payload: Dict[str, object] = {
            "input_excerpt": excerpt_basis or "",
            "outcome": actuation.status,
            "adapter": request.context.adapter_label,
            "reasons": actuation.reasons,
            "synthetic": True,
        }
        event = self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            agent_id=request.context.adapter_label,
            cause=latest_direction_id or governance_event_id or plan_anchor,
        )
        return actuation, event

    def _run_reflect(self, actuation: ActuationResult, caused_by: UUID | None) -> CognitiveEvent:
        verb = CognitiveVerb.REFLECT
        context = self._context or self._deps.state_repository.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        metrics = self._clock.stop(token)
        payload: Dict[str, object] = {"success": actuation.success, "reasons": actuation.reasons}
        event = self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            cause=caused_by,
        )
        self._deps.event_bus.emit_reflect(
            success=actuation.success,
            reasons=actuation.reasons,
            metrics=metrics,
            caused_by=event.event_id,
        )
        recorder = self._resolve_prompt_recorder(context)
        if recorder:
            rendered_reflect = (
                f"[reflect] success={actuation.success} | reasons={';'.join(actuation.reasons) or 'none'}"
            )
            self._record_prompt(
                recorder=recorder,
                phase="reflect",
                agent_id="reflect",
                rendered=rendered_reflect,
                role="system",
                kind="reflection",
                template_id="reflect.v1",
                tags=context.tags,
                event_id=event.event_id,
            )
        return event

    def _run_learn(self, actuation: ActuationResult, caused_by: UUID | None) -> CognitiveEvent:
        verb = CognitiveVerb.LEARN
        context = self._context or self._deps.state_repository.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        metrics = self._clock.stop(token)
        payload: Dict[str, object] = {
            "learn_path": "learn.jsonl",
            "learn_schema": "learn/1.0",
            "proposal_ids": [],
            "proposal_count": 0,
            "applied": False,
        }
        return self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            cause=caused_by,
        )

    def _record_plan_prompt(self, request: EpisodeRequest, plan: Sequence[PlanStep]) -> None:
        """
        Emit a minimal prompt provenance entry for the planner path.

        Uses a synthetic rendered prompt to validate end-to-end provenance plumbing
        without depending on external LLM providers.
        """
        recorder = self._resolve_prompt_recorder(request.context)
        if recorder is None:
            return
        goal = request.goal or "unspecified"
        step_summaries = ", ".join(step.description for step in plan) if plan else "no-steps"
        rendered = f"[planner.minimal] goal={goal} | steps={step_summaries}"
        self._record_prompt(
            recorder=recorder,
            phase="plan",
            agent_id="direction.planner",
            rendered=rendered,
            role="system",
            kind="system",
            template_id="planner.minimal.v1",
            tags=request.context.tags,
        )

    def _record_prompt(
        self,
        *,
        recorder: PromptRecorder,
        phase: str,
        agent_id: str,
        rendered: str,
        role: str | None,
        kind: str,
        template_id: str,
        tags: dict[str, object],
        event_id: UUID | None = None,
    ) -> None:
        """Append a prompt record if provenance is enabled."""
        if not recorder.is_enabled():
            return

        tag_strings = {
            str(k): str(v)
            for k, v in tags.items()
            if isinstance(v, (str, int, float, bool))
        }
        recorder.record(
            phase=phase,
            agent_id=agent_id,
            rendered=rendered,
            role=role,
            kind=kind,
            template_id=template_id,
            tags=tag_strings or None,
            event_id=str(event_id) if event_id is not None else None,
            now=self._now,
        )

    def _resolve_prompt_recorder(self, context: EpisodeContext) -> PromptRecorderPort | None:
        recorder = getattr(context, "prompt_recorder", None) or self._prompt_recorder
        if recorder is None:
            return None
        if not hasattr(recorder, "is_enabled") or not recorder.is_enabled():  # type: ignore[attr-defined]
            return None
        return recorder

    def _build_snapshot(self, request: EpisodeRequest, state: NoesisState) -> Dict[str, object]:
        using_label = request.using_label or request.context.adapter_label
        normalized = normalize_using(using_label)
        display_label = normalized.display if normalized else using_label
        snapshot_state = state.to_dict()
        episode_block = snapshot_state.get("episode")
        if isinstance(episode_block, dict):
            episode_block["using"] = display_label
        return {
            "task": request.goal,
            "seed": request.context.seed,
            "history": [],
            "tools_seen": [],
            "tags": request.context.tags,
            "state_path": "state.json",
            "state": snapshot_state,
            "using": display_label,
        }


class DirectiveApplicationError(RuntimeError):
    """Signals that a PlannerDirective could not be applied to the plan."""

    def __init__(self, *, directive: PlannerDirective, key: str, reason: str) -> None:
        self.directive_id = str(directive.directive_id)
        self.policy_id = directive.policy_id
        self.key = key
        self.reason = reason
        message = (
            f"Directive {self.directive_id} from {self.policy_id} cannot mutate '{key}': {reason}"
        )
        super().__init__(message)


_DESCRIPTION_PATTERN = re.compile(r"^plan\.steps\[(\d+)\]\.description$")
_KIND_PATTERN = re.compile(r"^plan\.steps\[(\d+)\]\.kind$")


def _apply_directive(plan: list[PlanStep], directive: PlannerDirective) -> None:
    for diff in directive.diff:
        key = diff.key.strip()
        match = _DESCRIPTION_PATTERN.fullmatch(key)
        if match:
            index = int(match.group(1))
            if not (0 <= index < len(plan)):
                raise DirectiveApplicationError(
                    directive=directive,
                    key=key,
                    reason=f"step index {index} is out of range",
                )
            if diff.after is None:
                raise DirectiveApplicationError(
                    directive=directive,
                    key=key,
                    reason="missing 'after' value for description",
                )
            plan[index].description = str(diff.after)
            continue

        match = _KIND_PATTERN.fullmatch(key)
        if match:
            index = int(match.group(1))
            if not (0 <= index < len(plan)):
                raise DirectiveApplicationError(
                    directive=directive,
                    key=key,
                    reason=f"step index {index} is out of range",
                )
            if diff.after is None:
                raise DirectiveApplicationError(
                    directive=directive,
                    key=key,
                    reason="missing 'after' value for kind",
                )
            try:
                plan[index].kind = PlanKind(str(diff.after))
            except ValueError as exc:
                raise DirectiveApplicationError(
                    directive=directive,
                    key=key,
                    reason=f"invalid plan kind '{diff.after}'",
                ) from exc
            continue

        raise DirectiveApplicationError(
            directive=directive,
            key=key,
            reason="unsupported diff key",
        )


def _with_stable_directive_id(directive: PlannerDirective, episode_id: str) -> PlannerDirective:
    """Attach a deterministic UUIDv5 legacy ID derived from the episode."""
    step_index = _extract_directive_step_index(directive)
    rule = f"{directive.policy_id}:{directive.reason or 'directive'}"
    stable_id = directive_uuid(episode_id, step_index, rule)
    return replace(directive, legacy_directive_id=stable_id)


def _with_stable_governance_id(result: GovernanceResult, episode_id: str) -> GovernanceResult:
    """Attach a deterministic UUIDv5 decision ID derived from the episode."""
    rule_token = result.rule_id or result.policy_id or result.decision.value
    stable_id = governance_uuid(episode_id, rule_token)
    return replace(result, decision_id=stable_id)


def _extract_directive_step_index(directive: PlannerDirective) -> int:
    for diff in directive.diff:
        index = _match_step_index(diff.key)
        if index is not None:
            return index
    return 0


def _match_step_index(key: str) -> int | None:
    normalized = key.strip()
    for pattern in (_DESCRIPTION_PATTERN, _KIND_PATTERN):
        match = pattern.fullmatch(normalized)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _parse_governance_mode(raw: object) -> GovernanceMode:
    if raw is None:
        return GovernanceMode.OFF
    if isinstance(raw, GovernanceMode):
        return raw
    normalized = str(raw).strip().lower()
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return GovernanceMode(normalized)


def _parse_failure_policy(raw: object, mode: GovernanceMode) -> GovernanceFailurePolicy:
    if raw is None:
        return GovernanceFailurePolicy.default_for(mode)
    if isinstance(raw, GovernanceFailurePolicy):
        return raw
    normalized = str(raw).strip().lower()
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return GovernanceFailurePolicy(normalized)


def _evaluate_governance(
    *,
    policy: PreActGovernor,
    goal: str,
    plan: Sequence[PlanStep],
    timeout_ms: int | None,
) -> GovernanceResult:
    if timeout_ms is None:
        return policy.evaluate(goal=goal, plan=plan)
    timeout_sec = max(timeout_ms, 1) / 1000.0
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(policy.evaluate, goal=goal, plan=plan)
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeoutError as exc:
            raise TimeoutError("governance_timeout") from exc


def _governance_error_payload(exc: Exception) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
    if isinstance(exc, TimeoutError):
        payload["timeout"] = True
    return payload


def _emit_governance_blocked_direction(
    *,
    event_bus: EventBus,
    plan: Sequence[PlanStep],
    governance_result: GovernanceResult,
    caused_by: UUID | None,
) -> UUID:
    directive = PlannerDirective(
        steps=[step.id for step in plan],
        status=DirectiveStatus.BLOCKED,
        reason="governance_veto",
        applied=False,
        policy_id=governance_result.policy_id,
        policy_version=governance_result.policy_version,
        policy_kind=governance_result.policy_kind,
    )
    payload = directive.to_mapping()
    payload.update(
        {
            "rule_id": governance_result.rule_id,
            "score": governance_result.score,
            "policy": governance_result.policy_id,
        }
    )
    return event_bus.emit_direction_payload(
        payload=payload,
        agent_id=governance_result.policy_id,
        caused_by=caused_by,
    )
