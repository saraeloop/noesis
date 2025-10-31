"""
Planner and actuator interfaces for Noēsis.

Defines the contracts the application layer depends on without binding to
concrete implementations or frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ..state import ActionRecord, NoesisState, PlanStep


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

    def emit_plan(self, *, steps: Sequence[PlanStep], rationale: str, source: str) -> None:
        ...

    def emit_action(self, action: ActionRecord) -> None:
        ...

    def emit_reflect(self, *, success: bool, reasons: list[str]) -> None:
        ...


class EpisodeRequest(Protocol):
    """Lightweight view of the episode context available to planners/actuators."""

    goal: str
    beliefs: tuple[str, ...]
    episode_id: str
    seed: int
    adapter_label: str
