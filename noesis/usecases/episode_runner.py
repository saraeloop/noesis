"""
Episode runner use case.

Coordinates planner and actuator dependencies to execute a cognitive episode
while keeping orchestration logic free from infrastructure concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from noesis.domain.planner.interfaces import (
    Actuator,
    ActuationResult,
    EventBus,
    Planner,
)
from noesis.domain.state import NoesisState, PlanStep
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository


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


class EpisodeRunner:
    """Application service orchestrating an episode via dependency injection."""

    def __init__(self, deps: EpisodeDependencies) -> None:
        self._deps = deps

    def run(self, request: EpisodeRequest) -> EpisodeResult:
        state = self._deps.state_repository.init(request.context)
        plan = self._deps.planner.build_plan(goal=request.goal, beliefs=request.beliefs)
        state.set_plan(steps=plan, rationale="minimal planner", source="planner.minimal")
        self._deps.event_bus.emit_plan(steps=plan, rationale="minimal planner", source="planner.minimal")

        actuation: ActuationResult = self._deps.actuator.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=self._deps.event_bus,
        )

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
