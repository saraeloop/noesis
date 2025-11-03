"""Meta-planning heuristics for Direction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from noesis.domain.faculties.direction import (
    DirectiveDiff,
    DirectiveStatus,
    PlannerDirective,
)
from noesis.domain.faculties.intuition import PolicyKind
from noesis.domain.state import PlanKind, PlanStep


def _describe_step(step: PlanStep) -> str:
    return f"{step.kind.value}:{step.description}".strip()


@dataclass(slots=True)
class MetaPlanner:
    """Deterministic depth/beam limited planner adjustments."""

    policy_id: str = "planner.meta"
    policy_version: str = "1.0.0"
    policy_kind: PolicyKind = "rules"
    depth: int = 2
    beam: int = 2

    def propose(
        self,
        *,
        goal: str,
        beliefs: Sequence[str],
        base_plan: Sequence[PlanStep],
    ) -> PlannerDirective:
        steps_summary: list[str] = []
        diffs: list[DirectiveDiff] = []
        applied = False

        steps_summary.append("meta:start")

        if base_plan:
            first_step = base_plan[0]
            if beliefs:
                before = first_step.description
                after = f"{before} ({len(beliefs)} beliefs)"
                if after != before:
                    diffs.append(
                        DirectiveDiff(
                            key="plan.steps[0].description",
                            before=before,
                            after=after,
                        )
                    )
                    steps_summary.append("heuristic:belief-context")
                    applied = True
            if first_step.kind == PlanKind.DETECT:
                first_step.rationale = "Bootstrap context before decomposition"

        if len(base_plan) > 1 and goal:
            second_step = base_plan[1]
            before = second_step.description
            if goal.lower() not in before.lower():
                after = f"Execute goal: {goal}".strip()
                diffs.append(
                    DirectiveDiff(
                        key="plan.steps[1].description",
                        before=before,
                        after=after,
                    )
                )
                steps_summary.append("heuristic:goal-alignment")
                applied = True

        if not applied:
            return PlannerDirective(
                steps=tuple(steps_summary or ("meta:start",)),
                status=DirectiveStatus.SKIPPED,
                reason="no-op",
                diff=tuple(diffs),
                applied=False,
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
            )

        return PlannerDirective(
            steps=tuple(steps_summary),
            status=DirectiveStatus.APPLIED,
            reason="heuristic-adjustment",
            diff=tuple(diffs),
            applied=True,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_kind=self.policy_kind,
        )
