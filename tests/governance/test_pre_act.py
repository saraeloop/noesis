from __future__ import annotations

from noesis import events as runtime_events
import noesis as ns
from noesis.domain.faculties.governance import GovernanceDecision, PreActGovernor
from noesis.domain.planner.meta import MetaPlanner
from noesis.domain.planner.minimal import MinimalPlanner, MinimalActuator
from noesis.domain.state import LineageTracker
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


def _plan(goal: str):
    return MinimalPlanner().build_plan(goal=goal, beliefs=())


def test_pre_act_vetoes_dangerous_goal() -> None:
    governor = PreActGovernor()
    result = governor.evaluate(goal="Danger zone", plan=_plan("Danger zone"))
    assert result.decision is GovernanceDecision.VETO
    assert result.rule_id == "rules.veto.danger"


def test_pre_act_audits_sensitive_goal() -> None:
    governor = PreActGovernor()
    result = governor.evaluate(goal="Write config", plan=_plan("Write config"))
    assert result.decision is GovernanceDecision.AUDIT
    assert result.rule_id == "rules.audit.sensitive"


def test_pre_act_allows_default_goal() -> None:
    governor = PreActGovernor()
    result = governor.evaluate(goal="Summarize report", plan=_plan("Summarize report"))
    assert result.decision is GovernanceDecision.ALLOW


def test_episode_runner_records_governance_veto(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="gov-ep",
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
    )
    instrumentation = EpisodeInstrumentation(clock=clock, emitter=emitter, lineage=lineage, hooks=())
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    runtime_events.start(run_dir, context.episode_id, {"task": context.task, "seed": context.seed})
    runtime_events.observe(run_dir, context.episode_id, task=context.task, tags=context.tags, snapshot=None)
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)
    result = runner.run(request)

    assert result.outcome.status == "vetoed"
    recorded = read_events(run_dir)
    decisions = [evt for evt in recorded if evt.get("phase") == "governance"]
    assert decisions and decisions[-1]["payload"]["decision"] == "veto"
    direction = [evt for evt in recorded if evt.get("phase") == "direction"]
    assert any(evt["payload"].get("status") == "blocked" for evt in direction)
    act_events = [evt for evt in recorded if evt.get("phase") == "act"]
    assert act_events and act_events[-1]["payload"]["outcome"] == "blocked"


def test_minimal_planner_emits_no_governance(tmp_path) -> None:
    runs_dir = tmp_path / "runs-min"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), planner_mode="minimal")
    try:
        episode_id = ns.run(task="Prepare summary", intuition=False)
        phases = {evt.get("phase") for evt in ns.events.read(episode_id)}
        assert "governance" not in phases
    finally:
        ns.set(runs_dir=original["runs_dir"], planner_mode=original.get("planner_mode", "meta"))
