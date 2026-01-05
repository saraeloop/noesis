from __future__ import annotations

from pathlib import Path

from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.faculties.governance import GovernanceMode, PreActGovernor
from noesis.domain.planner.minimal import MinimalPlanner
from noesis.infrastructure.state_repository import EpisodeContext
from noesis.interfaces.observability import RuntimeEventBus
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.domain.state import LineageTracker
from noesis.trace.events import read_events
from noesis.usecases.action_gating import govern_pre_act_action


def test_govern_pre_act_action_emits_candidate_and_governance(tmp_path: Path) -> None:
    run_dir = tmp_path / "gate"
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
    plan = MinimalPlanner().build_plan(goal="danger", beliefs=())
    candidate = ActionCandidate(
        id=None,
        kind="tool",
        payload={"tool_name": "fs.write", "args": {"path": "notes.txt"}},
        state_ref="state.json",
        state_hash="sha256:abc123",
        redaction=RedactionSpec(
            mode="hash_only",
            policy_id="redact.v1",
            policy_version="1.0.0",
            field_rules={},
        ),
        provenance={"plan_step_id": "step-2"},
        risk_tags=["destructive_fs"],
    )

    result = govern_pre_act_action(
        goal="danger",
        plan=plan,
        candidate=candidate,
        event_bus=event_bus,
        episode_id=context.episode_id,
        governance_policy=PreActGovernor(),
        governance_mode=GovernanceMode.ENFORCE,
        failure_policy=None,
        timeout_ms=None,
        caused_by=None,
    )

    assert result.candidate.id is not None
    assert result.should_execute is False
    assert result.terminal_outcome == "vetoed"
    assert result.governance_result is not None
    assert result.governance_event_id is not None

    events = read_events(run_dir)
    phases = [event.get("phase") for event in events]
    assert "action_candidate" in phases
    assert "governance" in phases
