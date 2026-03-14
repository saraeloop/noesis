from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from noesis.domain.planner.interfaces import ActuationResult, Actuator
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.state import LineageTracker
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.interfaces.observability import RuntimeEventBus
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.runtime.plan_projection import project_plan_state
from noesis.trace.events import read_events
from noesis.usecases.episode_runner import EpisodeDependencies, EpisodeRequest, EpisodeRunner


@dataclass(slots=True)
class _NoMutationActuator(Actuator):
    def execute(self, *, plan, request, state, event_bus):  # type: ignore[no-untyped-def]
        action = state.record_action(
            kind="adapter",
            tool="adapter:test",
            input_excerpt=request.goal,
            result_status="ok",
            step_id=plan[-1].id if plan else None,
        )
        event_bus.emit_action(action)
        return ActuationResult(
            status="ok",
            summary="done",
            metrics={"success": 1.0},
            reasons=[],
            success=True,
        )


def _make_runner(
    tmp_path: Path,
    *,
    planner,
    actuator,
    adapter_label: str,
) -> tuple[EpisodeRunner, EpisodeContext]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_projection",
        seed=0,
        task="Capture a projection-safe plan",
        tags={},
        adapter_label=adapter_label,
        started_at="2025-01-01T00:00:00Z",
    )
    deps = EpisodeDependencies(
        planner=planner,
        actuator=actuator,
        event_bus=RuntimeEventBus(
            context=context,
            emitter=CognitiveEventEmitter(run_dir=run_dir),
            lineage=LineageTracker(),
            clock=RuntimeClock(),
        ),
        state_repository=RuntimeStateRepository(context=context),
    )
    return EpisodeRunner(deps), context


def _read_state_plan(run_dir: Path) -> dict[str, object]:
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    plan = state.get("plan")
    assert isinstance(plan, dict)
    return plan


def test_project_plan_state_matches_persisted_minimal_plan(tmp_path: Path) -> None:
    runner, context = _make_runner(
        tmp_path,
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        adapter_label="adapter:core.minimal",
    )
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)

    runner.run(request)

    events = read_events(context.run_dir)
    projected = project_plan_state(events)
    assert projected is not None

    plan_event = next(event for event in events if event.get("phase") == "plan")
    act_events = [event for event in events if event.get("phase") == "act"]
    assert plan_event["payload"]["source"] == "planner.minimal"
    assert plan_event["payload"]["step_records"][0]["id"] == "step-1"
    assert all(event["payload"]["step_status"] == "done" for event in act_events)
    assert projected.to_dict() == _read_state_plan(context.run_dir)


def test_project_plan_state_preserves_pending_steps_without_step_status_evidence(tmp_path: Path) -> None:
    runner, context = _make_runner(
        tmp_path,
        planner=MinimalPlanner(),
        actuator=_NoMutationActuator(),
        adapter_label="adapter:test",
    )
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)

    runner.run(request)

    events = read_events(context.run_dir)
    projected = project_plan_state(events)
    assert projected is not None

    act_event = next(event for event in events if event.get("phase") == "act")
    assert "step_status" not in act_event["payload"]
    assert projected.to_dict() == _read_state_plan(context.run_dir)
