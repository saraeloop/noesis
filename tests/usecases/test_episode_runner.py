from pathlib import Path
from hashlib import sha256
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from noesis.domain.planner.interfaces import EventBus
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.state import ActionRecord, CognitiveEvent, CognitiveVerb, LineageTracker, NoesisState, PlanKind, PlanStep
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events, write_event
from noesis.usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    ResumeAnchor,
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
        evidence_ids=None,
        caused_by=None,
    ) -> UUID:
        return uuid4()

    def emit_action_candidate(  # type: ignore[override]
        self,
        *,
        candidate: ActionCandidate,
        caused_by=None,
    ) -> UUID:
        return uuid4()

    def emit_governance(self, *, result, caused_by=None) -> UUID:  # type: ignore[override]
        return uuid4()

    def emit_action(self, action: ActionRecord, *, metrics=None, step_status=None, caused_by=None) -> None:
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


def test_episode_runner_resume_uses_existing_plan_without_replanning(tmp_path):
    run_dir = Path(tmp_path)
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_resume",
        seed=0,
        task="Resume status report",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )
    state_repo = RuntimeStateRepository(context=context)
    state = state_repo.init(context)
    state.set_plan(
        steps=[PlanStep(id="step-1", kind=PlanKind.ACT, description="Continue from checkpoint")],
        rationale="resumed checkpoint",
        source="planner.resume",
    )
    state_repo.persist(state)

    event_bus = DummyEventBus()
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=event_bus,
        state_repository=state_repo,
    )
    checkpoint_parent_id = "00000000-0000-0000-0000-000000000001"
    resume_event_id = "00000000-0000-0000-0000-000000000002"
    write_event(
        run_dir,
        {
            "id": checkpoint_parent_id,
            "timestamp": "2025-01-01T00:00:00Z",
            "episode_id": context.episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": context.task},
            "evidence_ids": [],
        },
    )
    write_event(
        run_dir,
        {
            "id": resume_event_id,
            "timestamp": "2025-01-01T00:00:01Z",
            "episode_id": context.episode_id,
            "agent_id": "system",
            "phase": "runtime",
            "event_type": "run.resume",
            "payload": {"kind": "run.resume", "status": "resuming", "checkpoint_id": "chk_test"},
            "evidence_ids": [],
            "caused_by": checkpoint_parent_id,
        },
    )

    class _FileEventHistory:
        def read(self, run_dir: Path):
            return read_events(run_dir)

    instrumentation = EpisodeInstrumentation(
        clock=RuntimeClock(),
        emitter=CognitiveEventEmitter(run_dir=run_dir),
        lineage=LineageTracker(),
        event_history=_FileEventHistory(),
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)
    state_hash = f"sha256:{sha256((run_dir / 'state.json').read_bytes()).hexdigest()}"
    anchor = ResumeAnchor(
        checkpoint_id="chk_test",
        state_hash=state_hash,
        last_event_id=checkpoint_parent_id,
        resume_event_id=resume_event_id,
        event_offset=1,
    )
    result = runner.resume(request, anchor=anchor)

    assert result.outcome.status == "ok"
    assert result.outcome.success is True
    assert event_bus.plan_steps is None
    assert result.state.outcomes.actions
    events = read_events(run_dir)
    act_events = [event for event in events if event.get("phase") == "act"]
    assert act_events
    assert act_events[0].get("caused_by") == resume_event_id


def test_episode_runner_resume_rejects_anchor_state_hash_mismatch(tmp_path):
    run_dir = Path(tmp_path)
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_resume_mismatch",
        seed=0,
        task="Resume status report",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )
    state_repo = RuntimeStateRepository(context=context)
    state = state_repo.init(context)
    state.set_plan(
        steps=[PlanStep(id="step-1", kind=PlanKind.ACT, description="Continue from checkpoint")],
        rationale="resumed checkpoint",
        source="planner.resume",
    )
    state_repo.persist(state)

    checkpoint_parent_id = "00000000-0000-0000-0000-000000000011"
    resume_event_id = "00000000-0000-0000-0000-000000000012"
    write_event(
        run_dir,
        {
            "id": checkpoint_parent_id,
            "timestamp": "2025-01-01T00:00:00Z",
            "episode_id": context.episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": context.task},
            "evidence_ids": [],
        },
    )
    write_event(
        run_dir,
        {
            "id": resume_event_id,
            "timestamp": "2025-01-01T00:00:01Z",
            "episode_id": context.episode_id,
            "agent_id": "system",
            "phase": "runtime",
            "event_type": "run.resume",
            "payload": {"kind": "run.resume", "status": "resuming", "checkpoint_id": "chk_test"},
            "evidence_ids": [],
            "caused_by": checkpoint_parent_id,
        },
    )

    class _FileEventHistory:
        def read(self, run_dir: Path):
            return read_events(run_dir)

    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=DummyEventBus(),
        state_repository=state_repo,
    )
    instrumentation = EpisodeInstrumentation(
        clock=RuntimeClock(),
        emitter=CognitiveEventEmitter(run_dir=run_dir),
        lineage=LineageTracker(),
        event_history=_FileEventHistory(),
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)
    anchor = ResumeAnchor(
        checkpoint_id="chk_test",
        state_hash="sha256:deadbeef",
        last_event_id=checkpoint_parent_id,
        resume_event_id=resume_event_id,
        event_offset=1,
    )

    with pytest.raises(ValueError, match="state hash mismatch"):
        runner.resume(request, anchor=anchor)
