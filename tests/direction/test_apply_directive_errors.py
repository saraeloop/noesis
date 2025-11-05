from __future__ import annotations

import pytest

from noesis.domain.faculties.direction import DirectiveDiff, DirectiveStatus, PlannerDirective
from noesis.domain.state import PlanKind, PlanStep
from noesis.usecases.episode_runner import DirectiveApplicationError, _apply_directive


def _sample_plan() -> list[PlanStep]:
    return [
        PlanStep(id="step-0", kind=PlanKind.DETECT, description="Collect context"),
        PlanStep(id="step-1", kind=PlanKind.ACT, description="Execute goal"),
    ]


def test_apply_directive_rejects_out_of_range_index() -> None:
    directive = PlannerDirective(
        steps=("meta:start",),
        status=DirectiveStatus.APPLIED,
        reason="heuristic-adjustment",
        diff=(DirectiveDiff(key="plan.steps[4].description", before="A", after="B"),),
        applied=True,
        policy_id="planner.meta",
        policy_version="1.0.0",
        policy_kind="rules",
    )

    with pytest.raises(DirectiveApplicationError) as excinfo:
        _apply_directive(_sample_plan(), directive)

    message = str(excinfo.value)
    assert directive.policy_id in message
    assert str(directive.directive_id).startswith("dir-")
    assert directive.diff[0].key in message
    assert "out of range" in message


def test_apply_directive_enforces_exact_key_pattern() -> None:
    directive = PlannerDirective(
        steps=("meta:start",),
        status=DirectiveStatus.APPLIED,
        reason="heuristic-adjustment",
        diff=(
            DirectiveDiff(key="plan.steps[0].description_suffix", before="Collect context", after="Collect context (1)"),
        ),
        applied=True,
        policy_id="planner.meta",
        policy_version="1.0.0",
        policy_kind="rules",
    )

    with pytest.raises(DirectiveApplicationError) as excinfo:
        _apply_directive(_sample_plan(), directive)

    assert "unsupported diff key" in str(excinfo.value)
    assert directive.diff[0].key in str(excinfo.value)
