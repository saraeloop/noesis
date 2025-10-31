from noesis.domain.planner.minimal import MinimalPlanner
from noesis.domain.state import PlanKind


def test_minimal_planner_sequence():
    planner = MinimalPlanner()
    plan = planner.build_plan(goal="Investigate outage", beliefs=())
    kinds = [step.kind for step in plan]
    assert kinds == [PlanKind.DETECT, PlanKind.ACT, PlanKind.VERIFY]
    assert "Investigate outage" in plan[1].description
