"""
Deterministic plan-state projection from the canonical event stream.

This module keeps reconstruction logic pure so tests and diagnostics can
validate that the persisted plan snapshot remains derivable from
``events.jsonl`` plus stable runtime rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from noesis.domain.state import PlanKind, PlanStep, StepStatus


@dataclass(slots=True)
class ProjectedPlanState:
    """Structured plan snapshot reconstructed from runtime events."""

    steps: list[PlanStep]
    source: str
    updated_at: str
    rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the projected plan into the state.json shape."""
        payload: dict[str, Any] = {
            "steps": [step.to_dict() for step in self.steps],
            "source": self.source,
            "updated_at": self.updated_at,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        return payload


def project_plan_state(events: Sequence[Mapping[str, object]]) -> ProjectedPlanState | None:
    """Rebuild the plan portion of state.json from canonical runtime events."""
    latest_plan_index = -1
    latest_plan_event: Mapping[str, object] | None = None
    for index, event in enumerate(events):
        if event.get("phase") == "plan":
            latest_plan_index = index
            latest_plan_event = event
    if latest_plan_event is None:
        return None

    payload = latest_plan_event.get("payload")
    if not isinstance(payload, Mapping):
        return None

    steps = _project_plan_steps(payload)
    if not steps:
        return None

    projection = ProjectedPlanState(
        steps=steps,
        source=_string_value(payload.get("source")) or _string_value(latest_plan_event.get("agent_id")) or "system",
        updated_at=_string_value(latest_plan_event.get("timestamp")) or "",
        rationale=_optional_string(payload.get("rationale")),
    )
    for event in events[latest_plan_index + 1 :]:
        _apply_plan_step_status(projection.steps, event)
    return projection


def _project_plan_steps(payload: Mapping[str, object]) -> list[PlanStep]:
    step_records = payload.get("step_records")
    if isinstance(step_records, Sequence) and not isinstance(step_records, (str, bytes, bytearray)):
        steps = [_parse_step_record(item, index=index) for index, item in enumerate(step_records, start=1)]
        return [step for step in steps if step is not None]

    legacy_steps = payload.get("steps")
    if not isinstance(legacy_steps, Sequence) or isinstance(legacy_steps, (str, bytes, bytearray)):
        return []
    steps: list[PlanStep] = []
    for index, item in enumerate(legacy_steps, start=1):
        if not isinstance(item, str):
            continue
        steps.append(_parse_legacy_step_label(item, index=index))
    return steps


def _parse_step_record(payload: object, *, index: int) -> PlanStep | None:
    if not isinstance(payload, Mapping):
        return None

    raw_kind = _string_value(payload.get("kind"))
    raw_status = _string_value(payload.get("status"))
    step = PlanStep(
        id=_string_value(payload.get("id")) or f"step-{index}",
        kind=_coerce_plan_kind(raw_kind),
        description=_string_value(payload.get("description")) or "",
        status=_coerce_step_status(raw_status),
        rationale=_optional_string(payload.get("rationale")),
    )

    depends_on = payload.get("depends_on")
    if isinstance(depends_on, Sequence) and not isinstance(depends_on, (str, bytes, bytearray)):
        step.depends_on = [str(item) for item in depends_on if isinstance(item, str)]

    inputs = payload.get("inputs")
    if isinstance(inputs, Mapping):
        step.inputs = dict(inputs)

    outputs = payload.get("outputs")
    if isinstance(outputs, Mapping):
        step.outputs = dict(outputs)

    step.extensions = {
        str(key): value
        for key, value in payload.items()
        if isinstance(key, str) and key.startswith("x-")
    }
    return step


def _parse_legacy_step_label(label: str, *, index: int) -> PlanStep:
    kind_text, separator, description = label.partition(":")
    kind = _coerce_plan_kind(kind_text if separator else None)
    return PlanStep(
        id=f"step-{index}",
        kind=kind,
        description=description if separator else label,
        status=StepStatus.PENDING,
    )


def _apply_plan_step_status(steps: Sequence[PlanStep], event: Mapping[str, object]) -> None:
    if event.get("phase") != "act":
        return
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        return
    step_id = _string_value(payload.get("step_id"))
    step_status = _string_value(payload.get("step_status"))
    if not step_id or not step_status:
        return
    next_status = _coerce_step_status(step_status)
    for step in steps:
        if step.id == step_id:
            step.status = next_status
            return


def _coerce_plan_kind(value: str | None) -> PlanKind:
    if value is None:
        return PlanKind.DEFAULT
    try:
        return PlanKind(value)
    except ValueError:
        return PlanKind.DEFAULT


def _coerce_step_status(value: str | None) -> StepStatus:
    if value is None:
        return StepStatus.PENDING
    try:
        return StepStatus(value)
    except ValueError:
        return StepStatus.PENDING


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
