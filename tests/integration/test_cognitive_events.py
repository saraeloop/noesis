from pathlib import Path

from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.faculties.governance import PreActGovernor
from noesis.domain.state import CognitiveVerb, LineageTracker
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis import events
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events
from noesis.usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    EpisodeRunner,
)
from noesis.interfaces.observability import RuntimeEventBus


def _episode_context(tmp_path: Path) -> EpisodeContext:
    return EpisodeContext(
        run_dir=tmp_path,
        episode_id="ep_test",
        seed=0,
        task="Compute status",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )


def test_episode_runner_emits_metrics_and_lineage(tmp_path) -> None:
    ctx = _episode_context(Path(tmp_path))
    state_repo = RuntimeStateRepository(context=ctx)
    lineage = LineageTracker()
    clock = RuntimeClock()
    emitter = CognitiveEventEmitter(run_dir=ctx.run_dir)
    event_bus = RuntimeEventBus(context=ctx, emitter=emitter, lineage=lineage, clock=clock)
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label=ctx.adapter_label),
        event_bus=event_bus,
        state_repository=state_repo,
        direction_planner=MetaPlanner(),
        governance_policy=PreActGovernor(),
    )
    instrumentation = EpisodeInstrumentation(clock=clock, emitter=emitter, lineage=lineage, hooks=())
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    events.start(ctx.run_dir, ctx.episode_id, {"task": ctx.task, "seed": ctx.seed})
    events.observe(ctx.run_dir, ctx.episode_id, task=ctx.task, tags=ctx.tags, snapshot=None)

    request = EpisodeRequest(goal=ctx.task, beliefs=(), context=ctx)
    runner.run(request)

    recorded = read_events(ctx.run_dir)
    verbs = {e.get("phase"): e for e in recorded if e.get("phase") in {v.value for v in CognitiveVerb}}

    for verb in CognitiveVerb:
        if verb is CognitiveVerb.OBSERVE:
            continue
        assert verb.value in verbs
        record = verbs[verb.value]
        metrics = record.get("metrics")
        assert metrics, f"missing metrics for {verb.value}"
        assert metrics["duration_ms"] >= 0
        assert record.get("caused_by"), f"missing caused_by for {verb.value}"
