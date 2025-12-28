from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

from noesis.domain.planner.interfaces import EventBus
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.state import ActionRecord, CognitiveEvent, CognitiveVerb, NoesisState, PlanKind
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeRequest,
    EpisodeRunner,
)


class DummyEventBus(EventBus):
    def __init__(self) -> None:
        self.plan_steps = None
        self.actions: list[ActionRecord] = []
        self.reflected: tuple[bool, list[str]] | None = None

    def emit_plan(self, *, steps, rationale: str, source: str, metrics=None, caused_by=None) -> CognitiveEvent:  # type: ignore[override]
        self.plan_steps = list(steps)
        return CognitiveEvent(
            episode_id="ep_test",
            verb=CognitiveVerb.PLAN,
            payload={"steps": [step.id for step in steps]},
        )

    def emit_direction(self, *, directive, caused_by=None) -> UUID:  # type: ignore[override]
        return uuid4()

    def emit_direction_payload(  # type: ignore[override]
        self,
        *,
        payload: Mapping[str, object],
        agent_id: str,
        caused_by=None,
    ) -> UUID:
        return uuid4()

    def emit_governance(self, *, result, caused_by=None) -> UUID:  # type: ignore[override]
        return uuid4()

    def emit_action(self, action: ActionRecord, *, metrics=None, caused_by=None) -> None:
        self.actions.append(action)

    def emit_reflect(self, *, success: bool, reasons: list[str], metrics=None, caused_by=None) -> None:
        self.reflected = (success, reasons)


def test_episode_runner_executes_plan(tmp_path):
    run_dir = Path(tmp_path)
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_test",
        seed=0,
        task="Create status report",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )
    state_repo = RuntimeStateRepository(context=context)
    event_bus = DummyEventBus()
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=event_bus,
        state_repository=state_repo,
    )
    runner = EpisodeRunner(deps)
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)
    result = runner.run(request)

    assert result.outcome.status == "ok"
    assert result.outcome.success is True
    assert result.state.outcomes.status == "ok"
    assert event_bus.plan_steps[0].kind == PlanKind.DETECT  # type: ignore[index]
    assert event_bus.reflected == (True, ["step:step-1:detect", "step:step-2:act", "step:step-3:verify"])
