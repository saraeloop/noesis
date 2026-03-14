"""
Planner and actuator interfaces for Noēsis.

Defines the contracts the application layer depends on without binding to
concrete implementations or frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence
from uuid import UUID

from ..action_candidates import ActionCandidate
from ..state import ActionRecord, CognitiveEvent, CognitiveMetrics, NoesisState, PlanStep, StepStatus
from noesis.domain.faculties.direction import PlannerDirective
from noesis.domain.faculties.governance import GovernanceResult


@dataclass(slots=True)
class ActuationResult:
    """Outcome returned by an actuator after executing a plan."""

    status: str
    summary: str | None
    metrics: dict[str, float]
    reasons: list[str]
    success: bool


class Planner(Protocol):
    """Generates a sequence of plan steps for a given task."""

    def build_plan(self, *, goal: str, beliefs: Sequence[str]) -> list[PlanStep]:
        ...


class Actuator(Protocol):
    """
    Carries out plan steps and records actions on the state.

    Implementations must only mutate the provided state object and must not
    perform I/O beyond the injected event bus.
    """

    def execute(
        self,
        *,
        plan: Sequence[PlanStep],
        request: "EpisodeRequest",
        state: NoesisState,
        event_bus: "EventBus",
    ) -> ActuationResult:
        ...


class EventBus(Protocol):
    """Abstraction over runtime event emission (plan, act, reflect)."""

    def emit_plan(
        self,
        *,
        steps: Sequence[PlanStep],
        rationale: str,
        source: str,
        metrics: CognitiveMetrics | None = None,
        caused_by: UUID | None = None,
    ) -> CognitiveEvent:
        ...

    def emit_direction(
        self,
        *,
        directive: PlannerDirective,
        caused_by: UUID | None = None,
    ) -> UUID:
        ...

    def emit_direction_payload(
        self,
        *,
        payload: Mapping[str, object],
        agent_id: str,
        caused_by: UUID | None = None,
    ) -> UUID:
        ...

    def emit_action_candidate(
        self,
        *,
        candidate: ActionCandidate,
        caused_by: UUID | None = None,
    ) -> UUID:
        ...

    def emit_governance(
        self,
        *,
        result: GovernanceResult,
        caused_by: UUID | None = None,
    ) -> UUID:
        ...

    def emit_action(
        self,
        action: ActionRecord,
        *,
        metrics: CognitiveMetrics | None = None,
        step_status: StepStatus | str | None = None,
        caused_by: UUID | None = None,
    ) -> None:
        ...

    def emit_reflect(
        self,
        *,
        success: bool,
        reasons: list[str],
        metrics: CognitiveMetrics | None = None,
        caused_by: UUID | None = None,
    ) -> None:
        ...


class EpisodeRequest(Protocol):
    """Lightweight view of the episode context available to planners/actuators."""

    goal: str
    beliefs: tuple[str, ...]
    episode_id: str
    seed: int
    adapter_label: str
