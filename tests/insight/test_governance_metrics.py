from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from noesis import events as event_facade
from noesis.domain.faculties.governance import GovernanceMode, PreActGovernor
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.state import CognitiveEvent, CognitiveVerb, LineageTracker
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
from noesis.domain.faculties.insight import compute_metrics, build_insight_metrics


def _episode_context(tmp_path: Path, *, task: str) -> EpisodeContext:
    return EpisodeContext(
        run_dir=tmp_path,
        episode_id=f"ep-{task.replace(' ', '-').lower()}",
        seed=0,
        task=task,
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
    )


def _run_episode(tmp_path: Path, goal: str) -> Tuple[list[dict], dict, dict]:
    ctx = _episode_context(tmp_path, task=goal)
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
        governance_mode=GovernanceMode.AUDIT if "Provision" in goal else GovernanceMode.ENFORCE,
    )
    instrumentation = EpisodeInstrumentation(clock=clock, emitter=emitter, lineage=lineage, hooks=())
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    event_facade.start(ctx.run_dir, ctx.episode_id, {"task": ctx.task, "seed": ctx.seed})

    request = EpisodeRequest(goal=ctx.task, beliefs=(), context=ctx)
    runner.run(request)

    recorded = read_events(ctx.run_dir)
    summary_metrics = compute_metrics({}, recorded)
    insight = build_insight_metrics(recorded, summary_metrics).to_mapping()
    return recorded, summary_metrics, insight


def _run_minimal_episode(tmp_path: Path, goal: str) -> Tuple[list[dict], dict, dict]:
    ctx = _episode_context(tmp_path, task=goal)
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
        direction_planner=None,
        governance_policy=None,
    )
    instrumentation = EpisodeInstrumentation(clock=clock, emitter=emitter, lineage=lineage, hooks=())
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    event_facade.start(ctx.run_dir, ctx.episode_id, {"task": ctx.task, "seed": ctx.seed})

    request = EpisodeRequest(goal=ctx.task, beliefs=(), context=ctx)
    runner.run(request)

    recorded = read_events(ctx.run_dir)
    summary_metrics = compute_metrics({}, recorded)
    insight = build_insight_metrics(recorded, summary_metrics).to_mapping()
    return recorded, summary_metrics, insight


def _phase(records: Iterable[dict], phase: str) -> list[dict]:
    return [record for record in records if record.get("phase") == phase]


def test_success_episode_metrics(tmp_path) -> None:
    events, summary_metrics, insight = _run_episode(Path(tmp_path) / "ok", "Provision staging infra for the v0.8.0 release")

    assert insight["success"] is True
    assert insight["veto_count"] == 0
    assert insight["would_veto_count"] == 0
    assert insight["plan_adherence"] == 1.0
    assert insight["tool_coverage"] == 1.0
    assert insight["plan_revisions"] >= 0  # meta planner may adjust directives

    phase_ms = insight.get("phase_ms", {})
    for key in ("interpret", "plan"):
        assert isinstance(phase_ms.get(key), int)
        assert phase_ms[key] >= 1
    # Success run should include act/reflect timing
    for key in ("act", "reflect"):
        assert isinstance(phase_ms.get(key), int)
        assert phase_ms[key] >= 1

    governance_events = _phase(events, "governance")
    direction_events = _phase(events, "direction")
    if direction_events:
        assert direction_events[-1]["payload"]["status"] in {"applied", "skipped"}
    assert governance_events and governance_events[-1]["payload"]["decision"] in {"allow", "audit"}


def test_veto_episode_metrics_and_causality(tmp_path) -> None:
    events, summary_metrics, insight = _run_episode(
        Path(tmp_path) / "veto",
        "Danger operation: delete production database",
    )

    assert insight["success"] is False
    assert insight["veto_count"] >= 1
    assert insight["would_veto_count"] == 0
    assert insight["plan_adherence"] == 0.0
    assert insight["tool_coverage"] == 0.0

    phase_ms = insight.get("phase_ms", {})
    for key in ("interpret", "plan"):
        assert isinstance(phase_ms.get(key), int)
        assert phase_ms[key] >= 1
    # Enforce veto terminates before act/reflect
    assert phase_ms.get("act") in (None, 0)
    assert phase_ms.get("reflect") in (None, 0)

    plan_events = _phase(events, "plan")
    assert plan_events
    plan_id = plan_events[-1]["id"]

    blocked_directions = [
        ev for ev in _phase(events, "direction") if (ev.get("payload") or {}).get("status") == "blocked"
    ]
    assert blocked_directions, "expected a blocked direction after governance veto"
    blocked_id = blocked_directions[-1]["id"]
    assert blocked_directions[-1]["caused_by"] in {plan_id, *[ev.get("id") for ev in _phase(events, "direction")]}

    governance_events = _phase(events, "governance")
    assert governance_events and governance_events[-1]["payload"]["decision"] == "veto"
    governance_id = governance_events[-1]["id"]
    assert governance_events[-1]["caused_by"] == blocked_id

    act_events = _phase(events, "act")
    assert act_events == []


def test_minimal_mode_emits_no_direction_or_governance(tmp_path) -> None:
    events, summary_metrics, insight = _run_minimal_episode(
        Path(tmp_path) / "minimal",
        "Provision staging infra for the v0.8.0 release",
    )

    assert _phase(events, "direction") == []
    assert _phase(events, "governance") == []
    assert insight["plan_adherence"] == 1.0
    assert insight["veto_count"] == 0
    assert insight["would_veto_count"] == 0
    assert insight["tool_coverage"] == 1.0
