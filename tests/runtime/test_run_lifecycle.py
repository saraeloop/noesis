from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json

import pytest

import noesis as ns
from noesis.domain.run_lifecycle import (
    CheckpointConsistencyError,
    ResumeAdapterMismatchError,
    RunSealedError,
    RunLifecycleTransitionError,
)
from noesis.domain.state import PlanKind, PlanStep
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.runtime.paths import resolve_noesis_paths
from noesis.runtime.serialization import canonical_dumps
from noesis.trace.events import read_events, write_event


@contextmanager
def _preserve_config():
    original = ns.get()
    try:
        yield
    finally:
        ns.set(**original)


def _prepare_unsealed_run(*, runs_dir: Path, episode_id: str) -> Path:
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    run_dir = layout.episodes_dir / episode_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text('{"episode":{"id":"ep_test"}}\n', encoding="utf-8")
    write_event(
        run_dir,
        {
            "id": "evt-start",
            "timestamp": "2026-03-01T00:00:00Z",
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": "checkpoint smoke"},
            "evidence_ids": [],
        },
    )
    return run_dir


def _prepare_resumable_run(
    *,
    runs_dir: Path,
    episode_id: str,
    adapter_label: str = "adapter:core.minimal",
) -> Path:
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    run_dir = layout.episodes_dir / episode_id
    run_dir.mkdir(parents=True, exist_ok=True)
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id=episode_id,
        seed=0,
        task="resume continuation",
        tags={"test": "resume_run"},
        adapter_label=adapter_label,
        started_at="2026-03-05T00:00:00Z",
        process_id="proc_test_resume",
        process_name="resume-test",
        process_kind="oneshot",
        process_run_index=1,
    )
    state_repo = RuntimeStateRepository(context=context)
    state = state_repo.init(context)
    state.set_plan(
        steps=[PlanStep(id="step-1", kind=PlanKind.ACT, description="Continue execution")],
        rationale="resume checkpoint",
        source="planner.resume",
    )
    state_repo.persist(state)
    write_event(
        run_dir,
        {
            "id": "evt-start",
            "timestamp": "2026-03-05T00:00:00Z",
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": {"task": "resume continuation"},
            "evidence_ids": [],
        },
    )
    return run_dir


def test_checkpoint_and_resume_emit_causal_runtime_events(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_checkpoint_resume"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)

        checkpoint = ns.checkpoint(episode_id)
        assert checkpoint["run_id"] == episode_id
        assert checkpoint["schema_version"] == "checkpoint/1.0.0"
        assert isinstance(checkpoint["event_offset"], int)
        assert checkpoint["event_offset"] == 1
        assert "events" not in checkpoint

        checkpoint_id = str(checkpoint["checkpoint_id"])
        checkpoint_path = run_dir / "checkpoints" / checkpoint_id / "checkpoint.json"
        assert checkpoint_path.exists()

        checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint_payload["event_offset"] == 1
        assert checkpoint_payload["last_event_id"] == "evt-start"
        assert checkpoint_payload["state_hash"].startswith("sha256:")
        assert checkpoint_payload["artifact_manifest_hash"].startswith("sha256:")

        events_before_resume = read_events(run_dir)
        events_payload_before = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        checkpoint_events = [
            event
            for event in events_before_resume
            if event.get("phase") == "runtime" and event.get("event_type") == "run.checkpoint"
        ]
        assert checkpoint_events
        checkpoint_event = checkpoint_events[-1]
        assert checkpoint_event.get("caused_by") == "evt-start"
        assert (checkpoint_event.get("payload") or {}).get("kind") == "run.checkpoint"

        ns.resume(episode_id, checkpoint_id=checkpoint_id)

        events_after_resume = read_events(run_dir)
        events_payload_after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert events_after_resume[: len(events_before_resume)] == events_before_resume
        assert events_payload_after.startswith(events_payload_before)
        assert events_payload_after != events_payload_before
        resume_event = events_after_resume[-1]
        assert resume_event["phase"] == "runtime"
        assert resume_event["event_type"] == "run.resume"
        assert resume_event["payload"]["kind"] == "run.resume"
        assert resume_event["payload"]["checkpoint_id"] == checkpoint_id
        assert resume_event["caused_by"] == checkpoint_event["id"]


def test_interrupt_emits_runtime_event_with_causal_parent(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_interrupt"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        ns.interrupt(episode_id, reason="manual approval pending")

        events = read_events(run_dir)
        interrupt_events = [
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.interrupt"
        ]
        assert interrupt_events
        event = interrupt_events[-1]
        assert event.get("caused_by") == "evt-start"
        assert event["payload"]["kind"] == "run.interrupt"
        assert event["payload"]["status"] == "interrupted"


def test_seal_boundary_uses_final_marker_not_manifest_only(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_manifest_only"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        (run_dir / "manifest.json").write_text('{"schema_version":"manifest/1.0.0"}\n', encoding="utf-8")

        checkpoint = ns.checkpoint(episode_id)
        assert str(checkpoint["checkpoint_id"]).startswith("chk_")


def test_seal_boundary_blocks_when_final_marker_exists_even_without_manifest(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_final_only"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        (run_dir / "final.json").write_text('{"schema_version":"final/2.0.0"}\n', encoding="utf-8")

        with pytest.raises(RunSealedError):
            ns.checkpoint(episode_id)


def test_resume_rejects_sealed_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        episode_id = ns.run("sealed run", intuition=False)
        with pytest.raises(RunSealedError):
            ns.resume(episode_id, checkpoint_id="chk_missing")


def test_resume_rejects_history_mismatch_against_checkpoint_anchor(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_mismatch"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])

        events = read_events(run_dir)
        events[0]["id"] = "evt-tampered"
        payload = "\n".join(canonical_dumps(event) for event in events) + "\n"
        (run_dir / "events.jsonl").write_text(payload, encoding="utf-8")

        with pytest.raises(CheckpointConsistencyError):
            ns.resume(episode_id, checkpoint_id=checkpoint_id)


def test_resume_rejects_state_hash_mismatch_against_checkpoint(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_state_mismatch"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])

        (run_dir / "state.json").write_text('{"episode":{"id":"ep_tampered"}}\n', encoding="utf-8")

        with pytest.raises(CheckpointConsistencyError, match="state hash"):
            ns.resume(episode_id, checkpoint_id=checkpoint_id)


def test_resume_rejects_invalid_explicit_causal_anchor(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_bad_anchor"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        _ = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])

        with pytest.raises(CheckpointConsistencyError, match="resume caused_by"):
            ns.resume(
                episode_id,
                checkpoint_id=checkpoint_id,
                caused_by="evt-not-allowed",
            )


def test_checkpoint_rejects_transition_from_terminal_runtime_state(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_terminal_transition"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        run_dir = _prepare_unsealed_run(runs_dir=runs_dir, episode_id=episode_id)
        write_event(
            run_dir,
            {
                "id": "evt-vetoed",
                "timestamp": "2026-03-05T00:00:01Z",
                "episode_id": episode_id,
                "agent_id": "system",
                "phase": "terminate",
                "payload": {"status": "vetoed", "message": "governance veto"},
                "evidence_ids": [],
                "caused_by": "evt-start",
            },
        )
        with pytest.raises(RunLifecycleTransitionError, match="invalid run lifecycle transition"):
            ns.checkpoint(episode_id)


def test_resume_run_continues_same_run_and_seals(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_continue"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        run_dir = _prepare_resumable_run(runs_dir=runs_dir, episode_id=episode_id)
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])
        checkpoint_payload = json.loads(
            (run_dir / "checkpoints" / checkpoint_id / "checkpoint.json").read_text(encoding="utf-8")
        )
        assert checkpoint_payload["adapter_label"] == "core.minimal"
        events_before_resume = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        resumed_episode_id = ns.resume_run(episode_id, checkpoint_id=checkpoint_id)
        assert resumed_episode_id == episode_id

        events = read_events(run_dir)
        events_after_resume = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert events_after_resume.startswith(events_before_resume)
        assert events_after_resume != events_before_resume
        resume_event = next(
            event
            for event in reversed(events)
            if event.get("phase") == "runtime" and event.get("event_type") == "run.resume"
        )
        act_event = next(event for event in events if event.get("phase") == "act")
        assert act_event.get("caused_by") == resume_event["id"]
        assert (run_dir / "final.json").exists()

        with pytest.raises(RunSealedError):
            ns.resume_run(episode_id, checkpoint_id=checkpoint_id)


def test_resume_run_rejects_adapter_mismatch(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_adapter_mismatch"

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        run_dir = _prepare_resumable_run(
            runs_dir=runs_dir,
            episode_id=episode_id,
            adapter_label="adapter:graph.alpha",
        )
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])
        events_before = read_events(run_dir)

        with pytest.raises(ResumeAdapterMismatchError, match="adapter mismatch"):
            ns.resume_run(
                episode_id,
                checkpoint_id=checkpoint_id,
                using="graph.beta",
            )
        events_after = read_events(run_dir)
        before_resume_count = sum(
            1 for event in events_before if event.get("phase") == "runtime" and event.get("event_type") == "run.resume"
        )
        after_resume_count = sum(
            1 for event in events_after if event.get("phase") == "runtime" and event.get("event_type") == "run.resume"
        )
        assert after_resume_count == before_resume_count


def test_resume_run_non_minimal_preserves_adapter_label(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    episode_id = "ep_resume_non_minimal"

    class GraphAlpha:
        def invoke(self, payload):
            return payload

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        run_dir = _prepare_resumable_run(
            runs_dir=runs_dir,
            episode_id=episode_id,
            adapter_label="GraphAlpha",
        )
        checkpoint = ns.checkpoint(episode_id)
        checkpoint_id = str(checkpoint["checkpoint_id"])

        resumed_episode_id = ns.resume_run(
            episode_id,
            checkpoint_id=checkpoint_id,
            using=GraphAlpha(),
        )
        assert resumed_episode_id == episode_id
        events = read_events(run_dir)
        act_event = next(event for event in events if event.get("phase") == "act")
        assert (act_event.get("payload") or {}).get("tool") == "GraphAlpha"
        assert (act_event.get("payload") or {}).get("tool") != "core.minimal"


def test_governance_pause_mode_emits_interrupt_checkpoint_and_halts_side_effects(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    side_effect = workspace / "actuator-side-effect.txt"

    class MutatingGraph:
        def invoke(self, payload):
            side_effect.write_text(str(payload), encoding="utf-8")
            return payload

    with _preserve_config():
        ns.set(
            runs_dir=str(runs_dir),
            planner_mode="minimal",
            governance_mode="enforce",
            governance_pause_on_veto=True,
        )
        episode_id = ns.solve(
            task="Danger operation: delete production database",
            using=MutatingGraph(),
            intuition=False,
            workspace=workspace,
        )

        layout = resolve_noesis_paths(workspace=workspace, runs_dir=runs_dir)
        run_dir = layout.episodes_dir / episode_id
        events = read_events(run_dir)
        governance_event = next(
            event
            for event in events
            if event.get("phase") == "governance"
        )

        interrupt_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.interrupt"
        )
        checkpoint_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.checkpoint"
        )
        checkpoint_id = (checkpoint_event.get("payload") or {}).get("checkpoint_id")

        assert not side_effect.exists()
        assert interrupt_event.get("caused_by") == governance_event["id"]
        assert checkpoint_event.get("caused_by") == interrupt_event["id"]
        assert not any(event.get("phase") == "act" for event in events)
        assert not any(event.get("phase") == "terminate" for event in events)
        assert not (run_dir / "final.json").exists()
        assert not (run_dir / "manifest.json").exists()
        assert isinstance(checkpoint_id, str) and checkpoint_id
        assert (run_dir / "checkpoints" / checkpoint_id / "checkpoint.json").exists()

        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        outcomes = state.get("outcomes", {})
        assert outcomes.get("status") == "partial"
        assert "paused at checkpoint" in str(outcomes.get("summary", ""))
        assert outcomes.get("actions") == []


def test_enforce_non_veto_emits_single_governance_and_seals(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    class NoopGraph:
        def invoke(self, payload):
            return payload

    with _preserve_config():
        ns.set(
            runs_dir=str(runs_dir),
            planner_mode="minimal",
            governance_mode="enforce",
            governance_pause_on_veto=False,
        )
        episode_id = ns.solve(
            task="safe operation: list repository files",
            using=NoopGraph(),
            intuition=False,
        )

        run_dir = resolve_noesis_paths(workspace=None, runs_dir=runs_dir).episodes_dir / episode_id
        events = read_events(run_dir)
        governance_indices = [idx for idx, event in enumerate(events) if event.get("phase") == "governance"]
        candidate_indices = [idx for idx, event in enumerate(events) if event.get("phase") == "action_candidate"]

        assert len(governance_indices) == 1
        assert len(candidate_indices) == 1
        assert candidate_indices[0] < governance_indices[0]

        final_path = run_dir / "final.json"
        manifest_path = run_dir / "manifest.json"
        assert final_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert any(item.get("name") == "final.json" for item in manifest.get("files", []))
