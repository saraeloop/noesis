from __future__ import annotations

from noesis.domain.faculties.intuition import (
    IntuitionAssessment,
    RiskLevel,
    ScrutinyLevel,
    StrategyHint,
    ToolConstraint,
)
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.planner.minimal import MinimalPlanner
from noesis.domain.faculties.direction import DirectiveStatus


def test_meta_planner_generates_directive() -> None:
    planner = MetaPlanner()
    base_plan = MinimalPlanner().build_plan(goal="Review incidents", beliefs=("incident backlog",))

    directive = planner.propose(goal="Review incidents", beliefs=("incident backlog",), base_plan=base_plan)

    assert directive.status is DirectiveStatus.APPLIED
    assert directive.applied is True
    assert directive.policy_id == planner.policy_id
    diff_keys = {diff.key for diff in directive.diff}
    assert "plan.steps[0].description" in diff_keys
    assert "heuristic:belief-context" in directive.steps
    assert str(directive.directive_id).startswith("dir-")
    assert directive.legacy_directive_id


def test_meta_planner_no_beliefs_skips() -> None:
    planner = MetaPlanner()
    base_plan = MinimalPlanner().build_plan(goal="Document APIs", beliefs=())

    directive = planner.propose(goal="Document APIs", beliefs=(), base_plan=base_plan)

    assert directive.status is DirectiveStatus.SKIPPED
    assert directive.applied is False


def test_meta_planner_consumes_structured_intuition() -> None:
    planner = MetaPlanner()
    base_plan = MinimalPlanner().build_plan(goal="Review incidents", beliefs=())
    intuition = IntuitionAssessment(
        risk_level=RiskLevel.HIGH,
        strategy_hints=(StrategyHint.RETRIEVE_MORE, StrategyHint.VERIFY_FIRST),
        tool_constraints=(ToolConstraint.READ_ONLY,),
        scrutiny_level=ScrutinyLevel.STRICT,
    )

    directive = planner.propose(
        goal="Review incidents",
        beliefs=(),
        base_plan=base_plan,
        intuition=intuition,
    )

    assert directive.status is DirectiveStatus.APPLIED
    diff_keys = {diff.key for diff in directive.diff}
    assert "plan.steps[0].description" in diff_keys
    assert "plan.steps[1].description" in diff_keys
    assert "plan.steps[2].description" in diff_keys
    assert "intuition:risk-review" in directive.steps
    assert "intuition:read-only" in directive.steps
    assert "intuition:strict-scrutiny" in directive.steps
