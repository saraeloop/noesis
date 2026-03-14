from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.faculties.governance import (
    GovernanceDecision,
    GovernanceFailurePolicy,
    GovernanceMode,
    GovernanceResult,
    PreActGovernor,
)
from noesis.domain.planner.interfaces import ActuationResult, Actuator, Planner
from noesis.domain.state import LineageTracker, NoesisState, PlanKind, PlanStep
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.interfaces.observability import RuntimeEventBus
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events
from noesis.usecases.episode_runner import EpisodeDependencies, EpisodeRequest, EpisodeRunner


def _allow_result(goal: str) -> GovernanceResult:
    return GovernanceResult(
        decision=GovernanceDecision.ALLOW,
        rule_id="rules.allow.test",
        score=0.1,
        message="",
        policy_id="policy:test",
        policy_version="1.0.0",
        policy_kind="rules",
        details={"goal": goal},
    )


class VetoActionGovernor(PreActGovernor):
    policy_id = "policy:test"
    policy_version = "1.0.0"
    policy_kind = "rules"

    def evaluate(self, *, goal, plan):  # type: ignore[no-untyped-def]
        return _allow_result(goal)

    def evaluate_action(self, *, goal, plan, action):  # type: ignore[no-untyped-def]
        return GovernanceResult(
            decision=GovernanceDecision.VETO,
            rule_id="rules.veto.test",
            score=0.9,
            message="blocked",
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_kind=self.policy_kind,
            details={"goal": goal},
        )


class ErrorActionGovernor(PreActGovernor):
    policy_id = "policy:test"
    policy_version = "1.0.0"
    policy_kind = "rules"

    def evaluate(self, *, goal, plan):  # type: ignore[no-untyped-def]
        return _allow_result(goal)

    def evaluate_action(self, *, goal, plan, action):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


class AllowActionGovernor(PreActGovernor):
    policy_id = "policy:test"
    policy_version = "1.0.0"
    policy_kind = "rules"

    def evaluate(self, *, goal, plan):  # type: ignore[no-untyped-def]
        return _allow_result(goal)

    def evaluate_action(self, *, goal, plan, action):  # type: ignore[no-untyped-def]
        return _allow_result(goal)


@dataclass(slots=True)
class SingleStepPlanner(Planner):
    def build_plan(self, *, goal: str, beliefs, intuition=None):  # type: ignore[no-untyped-def]
        _ = beliefs, intuition
        return [PlanStep(id="step-1", kind=PlanKind.ACT, description=f"Execute {goal}")]


@dataclass(slots=True)
class CountingActuator(Actuator):
    called: int = 0

    def execute(self, *, plan, request, state, event_bus):  # type: ignore[no-untyped-def]
        self.called += 1
        action = state.record_action(
            kind="tool",
            tool=request.context.adapter_label,
            input_excerpt="run",
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


def _make_deps(
    tmp_path: Path,
    governor: PreActGovernor,
    *,
    failure_policy=None,
    mode: GovernanceMode = GovernanceMode.ENFORCE,
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_gate",
        seed=0,
        task="safe",
        tags={},
        adapter_label="adapter:tooling",
        started_at="2025-01-01T00:00:00Z",
    )
    state_repo = RuntimeStateRepository(context=context)
    event_bus = RuntimeEventBus(
        context=context,
        emitter=CognitiveEventEmitter(run_dir=run_dir),
        lineage=LineageTracker(),
        clock=RuntimeClock(),
    )
    actuator = CountingActuator()
    deps = EpisodeDependencies(
        planner=SingleStepPlanner(),
        actuator=actuator,
        event_bus=event_bus,
        state_repository=state_repo,
        governance_policy=governor,
        governance_mode=mode,
        governance_failure_policy=failure_policy,
    )
    return deps, context, actuator


def test_episode_runner_blocks_vetoed_action(tmp_path: Path) -> None:
    deps, context, actuator = _make_deps(tmp_path, VetoActionGovernor())
    runner = EpisodeRunner(deps)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    result = runner.run(request)

    assert actuator.called == 0
    assert result.outcome.status == "vetoed"
    events = read_events(context.run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
    assert "act" not in phases


def test_episode_runner_blocks_fail_closed_error(tmp_path: Path) -> None:
    deps, context, actuator = _make_deps(
        tmp_path,
        ErrorActionGovernor(),
        failure_policy=GovernanceFailurePolicy.FAIL_CLOSED,
    )
    runner = EpisodeRunner(deps)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    result = runner.run(request)

    assert actuator.called == 0
    assert result.outcome.status == "error"
    assert "governance_failure" in result.outcome.reasons
    events = read_events(context.run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
    assert "act" not in phases


def test_episode_runner_allows_action_and_emits_lineage(tmp_path: Path) -> None:
    deps, context, actuator = _make_deps(tmp_path, AllowActionGovernor())
    runner = EpisodeRunner(deps)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    result = runner.run(request)

    assert actuator.called == 1
    assert result.outcome.status == "ok"
    events = read_events(context.run_dir)
    candidate_event = next(event for event in events if event.get("phase") == "action_candidate")
    candidate_event_id = candidate_event["id"]
    governance_event = next(
        event for event in events if event.get("phase") == "governance" and event.get("caused_by") == candidate_event_id
    )
    act_event = next(
        event
        for event in events
        if event.get("phase") == "act"
        and event.get("payload", {}).get("action_candidate_id")
        == candidate_event.get("payload", {}).get("action_candidate_id")
    )
    assert act_event.get("caused_by") == governance_event["id"]


def test_episode_runner_audit_mode_allows_vetoed_action(tmp_path: Path) -> None:
    deps, context, actuator = _make_deps(
        tmp_path,
        VetoActionGovernor(),
        mode=GovernanceMode.AUDIT,
    )
    runner = EpisodeRunner(deps)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    result = runner.run(request)

    assert actuator.called == 1
    assert result.outcome.status == "ok"
    events = read_events(context.run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
    assert "act" in phases
