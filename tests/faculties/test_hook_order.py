from __future__ import annotations

from pathlib import Path

import pytest

from noesis import events as runtime_events
from noesis.domain.faculties.hooks import validate_hook_sequence
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.state import LineageTracker
from noesis.governance import GovernanceMode, PreActGovernor
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.interfaces.observability import RuntimeEventBus
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events
from noesis.usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    EpisodeRunner,
)


def test_validate_hook_sequence_accepts_good_ordering() -> None:
    sequence = [
        "observe",
        "intuition",
        "interpret",
        "plan",
        "direction",
        "governance",
        "terminate",
        "insight",
        "memory",
    ]
    validate_hook_sequence(sequence)


def test_validate_hook_sequence_rejects_bad_ordering() -> None:
    with pytest.raises(ValueError):
        validate_hook_sequence(["observe", "governance", "direction", "terminate"])
    with pytest.raises(ValueError):
        validate_hook_sequence(["observe", "plan", "act", "interpret"])


def test_enforce_veto_orders_direction_before_governance(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-order"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="hook-order-ep",
        seed=0,
        task="Danger operation",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )
    state_repo = RuntimeStateRepository(context=context)
    lineage = LineageTracker()
    clock = RuntimeClock()
    emitter = CognitiveEventEmitter(run_dir=context.run_dir)
    event_bus = RuntimeEventBus(
        context=context,
        emitter=emitter,
        lineage=lineage,
        clock=clock,
    )
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label=context.adapter_label),
        event_bus=event_bus,
        state_repository=state_repo,
        direction_planner=MetaPlanner(),
        governance_policy=PreActGovernor(),
        governance_mode=GovernanceMode.ENFORCE,
    )
    instrumentation = EpisodeInstrumentation(clock=clock, emitter=emitter, lineage=lineage, hooks=())
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    runtime_events.start(run_dir, context.episode_id, {"task": context.task, "seed": context.seed})
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)
    result = runner.run(request)
    assert result.outcome.status == "vetoed"

    recorded = read_events(run_dir)
    phases = [evt.get("phase") for evt in recorded if isinstance(evt.get("phase"), str)]
    validate_hook_sequence(phases)
    assert "direction" in phases and "governance" in phases
    assert phases.index("direction") < phases.index("governance")
    assert "act" not in phases
    terminate = [evt for evt in recorded if evt.get("phase") == "terminate"]
    assert terminate and terminate[-1]["payload"]["status"] == "vetoed"
