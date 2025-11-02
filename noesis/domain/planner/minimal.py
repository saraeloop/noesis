"""
Minimal planner and actuator implementations.

Provides an in-process fallback capable of running an entire episode without
external graphs or adapters. Keeps the logic deterministic and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .interfaces import ActuationResult, Actuator, EventBus, Planner
from ..state import (
    ActionRecord,
    NoesisState,
    PlanKind,
    PlanStep,
    StepStatus,
)


@dataclass(slots=True)
class MinimalPlanner(Planner):
    """Maps the goal into a deterministic detect → act → verify plan."""

    def build_plan(self, *, goal: str, beliefs: Sequence[str]) -> list[PlanStep]:
        description_suffix = goal if goal else "task"
        return [
            PlanStep(id="step-1", kind=PlanKind.DETECT, description="Collect relevant context"),
            PlanStep(id="step-2", kind=PlanKind.ACT, description=f"Execute goal: {description_suffix}"),
            PlanStep(id="step-3", kind=PlanKind.VERIFY, description="Verify outcome and capture learnings"),
        ]


@dataclass(slots=True)
class MinimalActuator(Actuator):
    """Executes minimal plans by recording synthetic adapter/tool actions."""

    tool_label: str = "adapter:core.minimal"

    def execute(
        self,
        *,
        plan: Sequence[PlanStep],
        request: "EpisodeRequest",
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        reasons: list[str] = []
        for step in plan:
            step.status = StepStatus.DONE
            action = state.record_action(
                kind="adapter",
                tool=self.tool_label,
                input_excerpt=step.description,
                result_status="ok",
                step_id=step.id,
            )
            event_bus.emit_action(action)
            reasons.append(f"step:{step.id}:{step.kind.value}")

        return ActuationResult(
            status="ok",
            summary=f"Completed {len(plan)} minimal steps.",
            metrics={"task_score": 0.75, "goal_success": 0.8, "efficiency": 0.7},
            reasons=reasons,
            success=True,
        )
