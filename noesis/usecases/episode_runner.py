"""
Episode runner use case.

Coordinates planner and actuator dependencies to execute a cognitive episode
while keeping orchestration logic free from infrastructure concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence
from uuid import UUID

from noesis.domain.planner.interfaces import (
    Actuator,
    ActuationResult,
    EventBus,
    Planner,
)
from noesis.domain.state import CognitiveEvent, CognitiveMetrics, CognitiveVerb, LineageTracker, NoesisState, PlanStep
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
        plan, plan_event = self._run_plan(request, state)
        actuation, act_event = self._run_act(plan, request, state)
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

    def _run_plan(self, request: EpisodeRequest, state: NoesisState) -> tuple[list[PlanStep], CognitiveEvent]:
        verb = CognitiveVerb.PLAN
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        plan = self._deps.planner.build_plan(goal=request.goal, beliefs=request.beliefs)
        metrics = self._clock.stop(token)
        labels = [f"{step.kind.value}:{step.description}" for step in plan]
        payload: Dict[str, object] = {
            "steps": labels,
            "rationale": "minimal planner",
            "source": "planner.minimal",
        }
        event = self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            agent_id="planner.minimal",
        )
        state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
        self._deps.event_bus.emit_plan(
            steps=plan,
            rationale="minimal planner",
            source="planner.minimal",
            metrics=metrics,
            caused_by=event.event_id,
        )
        return plan, event

    def _run_act(
        self,
        plan: Sequence[PlanStep],
        request: EpisodeRequest,
        state: NoesisState,
    ) -> tuple[ActuationResult, CognitiveEvent]:
        verb = CognitiveVerb.ACT
        context = request.context
        self._hooks.before_phase(verb, context)
        token = self._clock.start(verb)
        actuation = self._deps.actuator.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=self._deps.event_bus,
        )
        metrics = self._clock.stop(token)
        excerpt_basis = plan[0].description if plan else request.goal
        payload: Dict[str, object] = {
            "input_excerpt": excerpt_basis or "",
            "outcome": actuation.status,
            "adapter": request.context.adapter_label,
            "reasons": actuation.reasons,
        }
        event = self._emit_event(
            verb=verb,
            context=context,
            payload=payload,
            metrics=metrics,
            agent_id=request.context.adapter_label,
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
