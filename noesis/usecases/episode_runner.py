"""
Episode runner use case.

Coordinates planner and actuator dependencies to execute a cognitive episode
while keeping orchestration logic free from infrastructure concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from noesis.domain.planner.interfaces import (
    Actuator,
    ActuationResult,
    EventBus,
    Planner,
)
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.faculties.direction import PlannerDirective, DirectiveStatus
from noesis.domain.faculties.governance import GovernanceDecision, GovernanceResult, PreActGovernor
from noesis.domain.state import CognitiveEvent, CognitiveMetrics, CognitiveVerb, LineageTracker, NoesisState, PlanKind, PlanStep, OUTCOME_STATUS_VETOED
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events
from .hooks.meta_phase import CompositeMetaPhaseHook, MetaPhaseHook, NullMetaPhaseHook


@dataclass(slots=True)
class EpisodeRequest:
    goal: str
    beliefs: tuple[str, ...]
    context: EpisodeContext


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
    state_repository: RuntimeStateRepository
    direction_planner: MetaPlanner | None = None
    governance_policy: PreActGovernor | None = None


@dataclass(slots=True)
class EpisodeInstrumentation:
    clock: RuntimeClock
    emitter: CognitiveEventEmitter
    lineage: LineageTracker
    hooks: Sequence[MetaPhaseHook] = field(default_factory=lambda: (NullMetaPhaseHook(),))


class EpisodeRunner:
    """Application service orchestrating an episode via dependency injection."""

    def __init__(
        self,
        deps: EpisodeDependencies,
        *,
        instrumentation: EpisodeInstrumentation | None = None,
    ) -> None:
        self._deps = deps
        context = getattr(deps.state_repository, "context", None)
        if instrumentation is None:
            if context is None:
                raise ValueError("EpisodeRunner requires instrumentation or a repository context")
            instrumentation = EpisodeInstrumentation(
                clock=RuntimeClock(),
                emitter=CognitiveEventEmitter(run_dir=context.run_dir),
                lineage=LineageTracker(),
                hooks=(NullMetaPhaseHook(),),
            )
        self._clock = instrumentation.clock
        self._emitter = instrumentation.emitter
        self._lineage = instrumentation.lineage
        hooks = instrumentation.hooks or (NullMetaPhaseHook(),)
        self._hooks = CompositeMetaPhaseHook(tuple(hooks))
        self._context = context

    def run(self, request: EpisodeRequest) -> EpisodeResult:
        context = request.context
        self._seed_lineage(context)
        state = self._deps.state_repository.init(request.context)

        interpret_event = self._run_interpret(request)
        plan, plan_event, direction_event_id = self._run_plan(request, state)
        actuation, act_event = self._run_act(plan, plan_event, direction_event_id, request, state)
        reflect_event = self._run_reflect(actuation, plan_event.event_id)
        self._run_learn(actuation, reflect_event.event_id)

        state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
        state.set_outcome(status=actuation.status, summary=actuation.summary, metrics=actuation.metrics)
        self._deps.state_repository.persist(state)

        outcome = EpisodeOutcome(
            status=actuation.status,
            success=actuation.success,
            summary=actuation.summary,
            metrics=actuation.metrics,
            reasons=actuation.reasons,
        )
        return EpisodeResult(state=state, outcome=outcome, plan=plan)

    def _seed_lineage(self, context: EpisodeContext) -> None:
        events = read_events(context.run_dir)
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
        event = CognitiveEvent(
            episode_id=context.episode_id,
            verb=verb,
            payload=payload,
        ).with_metrics(metrics)
        linked = self._lineage.register(event, cause=cause)
        self._emitter.emit(linked, agent_id=agent_id)
        self._hooks.after_phase(verb, context, linked)
        return linked

    def _run_interpret(self, request: EpisodeRequest) -> CognitiveEvent:
        verb = CognitiveVerb.INTERPRET
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        signals = list(request.beliefs)
        metrics = self._clock.stop(token)
        payload: Dict[str, object] = {"signals": signals}
        return self._emit_event(verb=verb, context=context, payload=payload, metrics=metrics)

    def _run_plan(
        self,
        request: EpisodeRequest,
        state: NoesisState,
    ) -> tuple[list[PlanStep], CognitiveEvent, Optional[UUID]]:
        verb = CognitiveVerb.PLAN
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan = self._deps.planner.build_plan(goal=request.goal, beliefs=request.beliefs)
        directive: PlannerDirective | None = None
        if self._deps.direction_planner is not None:
            directive = self._deps.direction_planner.propose(
                goal=request.goal,
                beliefs=request.beliefs,
                base_plan=plan,
            )
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
    ) -> tuple[ActuationResult, CognitiveEvent]:
        verb = CognitiveVerb.ACT
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan_anchor = plan_event.event_id
        latest_direction_id: Optional[UUID] = direction_event_id
        governance_result: GovernanceResult | None = None
        governance_event_id: Optional[UUID] = None
        if self._deps.governance_policy is not None:
            governance_result = self._deps.governance_policy.evaluate(goal=request.goal, plan=plan)
            governance_event_id = self._deps.event_bus.emit_governance(
                result=governance_result,
                caused_by=latest_direction_id or plan_anchor,
            )
            if governance_result.decision is GovernanceDecision.VETO:
                veto_directive = PlannerDirective(
                    steps=("governance:veto", governance_result.rule_id),
                    status=DirectiveStatus.BLOCKED,
                    reason="veto",
                    diff=(),
                    applied=False,
                    policy_id=governance_result.policy_id,
                    policy_version=governance_result.policy_version,
                    policy_kind=governance_result.policy_kind,
                )
                latest_direction_id = self._deps.event_bus.emit_direction(
                    directive=veto_directive,
                    caused_by=governance_event_id,
                )
                metrics = self._clock.stop(token)
                excerpt_basis = plan[0].description if plan else request.goal
                payload: Dict[str, object] = {
                    "input_excerpt": excerpt_basis or "",
                    "outcome": "blocked",
                    "adapter": request.context.adapter_label,
                    "reasons": [governance_result.rule_id],
                }
                event = self._emit_event(
                    verb=verb,
                    context=context,
                    payload=payload,
                    metrics=metrics,
                    agent_id=request.context.adapter_label,
                    cause=latest_direction_id,
                )
                return (
                    ActuationResult(
                        status=OUTCOME_STATUS_VETOED,
                        summary=governance_result.message or "Action vetoed",
                        metrics={},
                        reasons=[governance_result.rule_id],
                        success=False,
                    ),
                    event,
                )
        actuation = self._deps.actuator.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=self._deps.event_bus,
        )
        if governance_result and governance_result.decision is GovernanceDecision.AUDIT:
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
        return event

    def _run_learn(self, actuation: ActuationResult, caused_by: UUID | None) -> CognitiveEvent:
        verb = CognitiveVerb.LEARN
        context = self._context or self._deps.state_repository.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        metrics = self._clock.stop(token)
        payload: Dict[str, object] = {
            "policy_id": "policy:core.minimal",
            "basis": actuation.reasons,
            "proposal": [],
            "applied": False,
            "scope": "episode",
        }
        return self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            cause=caused_by,
        )
def _apply_directive(plan: list[PlanStep], directive: PlannerDirective) -> None:
    for diff in directive.diff:
        key = diff.key
        if key.startswith("plan.steps[") and key.endswith("].description"):
            index_str = key[len("plan.steps[") : -len("].description")]
            try:
                index = int(index_str)
            except ValueError:
                continue
            if 0 <= index < len(plan) and diff.after is not None:
                plan[index].description = str(diff.after)
        elif key.startswith("plan.steps[") and key.endswith("].kind") and diff.after:
            index_str = key[len("plan.steps[") : -len("].kind")]
            try:
                index = int(index_str)
            except ValueError:
                continue
            if 0 <= index < len(plan):
                try:
                    plan[index].kind = PlanKind(str(diff.after))
                except ValueError:
                    continue
