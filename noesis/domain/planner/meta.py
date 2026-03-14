"""Meta-planning heuristics for Direction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from noesis.domain.faculties.direction import (
    DirectiveDiff,
    DirectiveStatus,
    PlannerDirective,
)
from noesis.domain.faculties.intuition import (
    IntuitionAssessment,
    PolicyKind,
    RiskLevel,
    ScrutinyLevel,
    StrategyHint,
    ToolConstraint,
)
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
        intuition: IntuitionAssessment | None = None,
    ) -> PlannerDirective:
        steps_summary: list[str] = []
        diffs: list[DirectiveDiff] = []
        applied = False

        steps_summary.append("meta:start")

        if base_plan:
            first_step = base_plan[0]
            first_after = first_step.description
            if beliefs:
                first_after = f"{first_after} ({len(beliefs)} beliefs)"
                if first_after != first_step.description:
                    steps_summary.append("heuristic:belief-context")
                    applied = True
            if intuition is not None:
                if intuition.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
                    if "risk review" not in first_after.lower():
                        first_after = f"{first_after} with risk review"
                    steps_summary.append("intuition:risk-review")
                    applied = True
                if StrategyHint.RETRIEVE_MORE in intuition.strategy_hints:
                    if "supporting evidence" not in first_after.lower():
                        first_after = f"{first_after} and retrieve supporting evidence"
                    steps_summary.append("intuition:retrieve-more")
                    applied = True
            if first_after != first_step.description:
                diffs.append(
                    DirectiveDiff(
                        key="plan.steps[0].description",
                        before=first_step.description,
                        after=first_after,
                    )
                )
            if first_step.kind == PlanKind.DETECT:
                first_step.rationale = "Bootstrap context before decomposition"

        if len(base_plan) > 1 and goal:
            second_step = base_plan[1]
            before = second_step.description
            after = before
            if goal.lower() not in before.lower():
                after = f"Execute goal: {goal}".strip()
                steps_summary.append("heuristic:goal-alignment")
                applied = True
            if intuition is not None:
                if StrategyHint.NARROW_SCOPE in intuition.strategy_hints:
                    after = f"Execute constrained goal: {goal}".strip()
                    steps_summary.append("intuition:narrow-scope")
                    applied = True
                if ToolConstraint.READ_ONLY in intuition.tool_constraints:
                    after = f"Execute read-only analysis for goal: {goal}".strip()
                    steps_summary.append("intuition:read-only")
                    applied = True
                if ToolConstraint.NO_SIDE_EFFECTS in intuition.tool_constraints:
                    after = f"Execute no-side-effect analysis for goal: {goal}".strip()
                    steps_summary.append("intuition:no-side-effects")
                    applied = True
            if after != before:
                diffs.append(
                    DirectiveDiff(
                        key="plan.steps[1].description",
                        before=before,
                        after=after,
                    )
                )

        if len(base_plan) > 2 and intuition is not None:
            verify_step = base_plan[2]
            before = verify_step.description
            after = before
            if intuition.scrutiny_level is ScrutinyLevel.ELEVATED:
                after = "Verify outcome with elevated scrutiny"
                steps_summary.append("intuition:elevated-scrutiny")
                applied = True
            elif intuition.scrutiny_level is ScrutinyLevel.STRICT:
                after = "Verify outcome with strict boundary checks"
                steps_summary.append("intuition:strict-scrutiny")
                applied = True
            if StrategyHint.VERIFY_FIRST in intuition.strategy_hints and "verify" in before.lower():
                after = "Verify outcome before finalizing agent response"
                steps_summary.append("intuition:verify-first")
                applied = True
            if after != before:
                diffs.append(
                    DirectiveDiff(
                        key="plan.steps[2].description",
                        before=before,
                        after=after,
                    )
                )

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
