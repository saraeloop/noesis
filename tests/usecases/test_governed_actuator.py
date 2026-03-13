from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.faculties.governance import (
    GovernanceFailurePolicy,
    GovernanceMode,
    PreActGovernor,
)
from noesis.domain.planner.interfaces import ActuationResult, Actuator
from noesis.domain.planner.minimal import MinimalPlanner
from noesis.domain.state import ActionArtifact, LineageTracker, NoesisState, Provenance
from noesis.infrastructure.state_repository import EpisodeContext
from noesis.interfaces.observability import RuntimeEventBus
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.trace.events import read_events
from noesis.usecases.actuation.governed_actuator import GovernedActuator
from noesis.usecases.episode_runner import EpisodeRequest


@dataclass(slots=True)
class StaticCandidateBuilder:
    candidate: ActionCandidate

    def build(self, *, plan, request, state):  # type: ignore[no-untyped-def]
        _ = (plan, request, state)
        return self.candidate


@dataclass(slots=True)
class RecordingActuator(Actuator):
    called: int = 0

    def execute(self, *, plan, request, state, event_bus):  # type: ignore[no-untyped-def]
        self.called += 1
        action = state.record_action(
            kind="tool",
            tool="demo",
            input_excerpt="demo",
            result_status="ok",
            step_id=plan[-1].id if plan else None,
            provenance=Provenance(source="unit-test", adapter_id="adapter:tooling"),
            result_artifacts=[
                ActionArtifact(
                    type="doc",
                    uri="artifact://demo/result",
                    sha256="sha256:" + "a" * 64,
                )
            ],
            extensions={"x-custom": "demo"},
        )
        event_bus.emit_action(action)
        return ActuationResult(
            status="ok",
            summary="done",
            metrics={"success": 1.0},
            reasons=[],
            success=True,
        )


class FaultyGovernor(PreActGovernor):
    def evaluate(self, *, goal, plan):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


def _make_context(tmp_path: Path) -> tuple[EpisodeContext, RuntimeEventBus, NoesisState]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_gate",
        seed=0,
        task="danger",
        tags={},
        adapter_label="adapter:tooling",
        started_at="2025-01-01T00:00:00Z",
    )
    event_bus = RuntimeEventBus(
        context=context,
        emitter=CognitiveEventEmitter(run_dir=run_dir),
        lineage=LineageTracker(),
        clock=RuntimeClock(),
    )
    state = NoesisState(
        episode_id=context.episode_id,
        seed=context.seed,
        task=context.task,
        started_at=context.started_at,
        tags=context.tags,
        adapter_label=context.adapter_label,
    )
    return context, event_bus, state


def _candidate() -> ActionCandidate:
    return ActionCandidate(
        id=None,
        kind="tool",
        payload={"tool_name": "fs.write", "args": {"path": "notes.txt"}},
        state_ref="state.json",
        state_hash="sha256:" + "a" * 64,
        redaction=RedactionSpec(
            mode="hash_only",
            policy_id="redact.v1",
            policy_version="1.0.0",
            field_rules={},
        ),
        provenance={"plan_step_id": "step-2"},
        risk_tags=["destructive_fs"],
    )


def test_governed_actuator_blocks_on_veto(tmp_path: Path) -> None:
    context, event_bus, state = _make_context(tmp_path)
    request = EpisodeRequest(goal="danger", beliefs=(), context=context)
    plan = MinimalPlanner().build_plan(goal=request.goal, beliefs=())
    inner = RecordingActuator()
    governed = GovernedActuator(
        inner=inner,
        candidate_builder=StaticCandidateBuilder(_candidate()),
        governance_policy=PreActGovernor(),
        governance_mode=GovernanceMode.ENFORCE,
        failure_policy=None,
        timeout_ms=None,
    )

    result = governed.execute(plan=plan, request=request, state=state, event_bus=event_bus)

    assert result.status == "vetoed"
    assert inner.called == 0
    events = read_events(context.run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
    assert "act" not in phases


def test_governed_actuator_blocks_on_fail_closed_error(tmp_path: Path) -> None:
    context, event_bus, state = _make_context(tmp_path)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    plan = MinimalPlanner().build_plan(goal=request.goal, beliefs=())
    inner = RecordingActuator()
    governed = GovernedActuator(
        inner=inner,
        candidate_builder=StaticCandidateBuilder(_candidate()),
        governance_policy=FaultyGovernor(),
        governance_mode=GovernanceMode.ENFORCE,
        failure_policy=GovernanceFailurePolicy.FAIL_CLOSED,
        timeout_ms=None,
    )

    result = governed.execute(plan=plan, request=request, state=state, event_bus=event_bus)

    assert result.status == "error"
    assert inner.called == 0
    events = read_events(context.run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
    assert "act" not in phases


def test_governed_actuator_allows_and_emits_act(tmp_path: Path) -> None:
    context, event_bus, state = _make_context(tmp_path)
    request = EpisodeRequest(goal="safe", beliefs=(), context=context)
    plan = MinimalPlanner().build_plan(goal=request.goal, beliefs=())
    inner = RecordingActuator()
    governed = GovernedActuator(
        inner=inner,
        candidate_builder=StaticCandidateBuilder(_candidate()),
        governance_policy=PreActGovernor(),
        governance_mode=GovernanceMode.ENFORCE,
        failure_policy=None,
        timeout_ms=None,
    )

    result = governed.execute(plan=plan, request=request, state=state, event_bus=event_bus)

    assert result.status == "ok"
    assert inner.called == 1
    events = read_events(context.run_dir)
    candidate = next(event for event in events if event.get("phase") == "action_candidate")
    governance = next(event for event in events if event.get("phase") == "governance")
    act = next(event for event in events if event.get("phase") == "act")
    action_state = state.actions[-1].to_dict()
    assert act["payload"]["action_candidate_id"] == candidate["payload"]["action_candidate_id"]
    assert act.get("caused_by") == governance["id"]
    assert act["payload"]["action_id"] == action_state["id"]
    assert act["payload"]["kind"] == action_state["kind"]
    assert act["payload"]["tool"] == action_state["tool"]
    assert act["payload"]["input_excerpt"] == action_state["input_excerpt"]
    assert act["payload"]["result_status"] == action_state["result_status"]
    assert act["payload"]["step_id"] == action_state["step_id"]
    assert act["payload"]["provenance"] == action_state["provenance"]
    assert act["payload"]["result_artifacts"] == action_state["result_artifacts"]
    assert act["payload"]["x-custom"] == action_state["x-custom"]
    assert act["payload"]["x-action_candidate_id"] == action_state["x-action_candidate_id"]
    assert action_state["timestamp"] == act["timestamp"]
