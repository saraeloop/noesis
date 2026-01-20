from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

from noesis.domain.planner.interfaces import EventBus
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.state import ActionRecord, CognitiveEvent, CognitiveVerb
from noesis.domain.verification import FileContainsAssertion, FileExistsAssertion
from noesis.infrastructure.snapshot import (
    FileSystemSnapshotGateway,
    FileSystemSnapshotMetadataStore,
    UtcSnapshotClock,
)
from noesis.infrastructure.immutability import ManifestSealStatus
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.infrastructure.verification import FileSystemFileReader
from noesis.interfaces.config import ConfigSnapshot
from noesis.runtime.summary import finalize_summary
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION
from noesis.usecases.episode_runner import EpisodeDependencies, EpisodeRequest, EpisodeRunner
from noesis.usecases.immutability import ArtifactImmutabilityGuard
from noesis.usecases.snapshot_artifacts import SnapshotArtifactWriter


class DummyEventBus(EventBus):
    def emit_plan(self, *, steps, rationale: str, source: str, metrics=None, caused_by=None) -> CognitiveEvent:  # type: ignore[override]
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

    def emit_action_candidate(  # type: ignore[override]
        self,
        *,
        candidate: ActionCandidate,
        caused_by=None,
    ) -> UUID:
        return uuid4()

    def emit_governance(self, *, result, caused_by=None) -> UUID:  # type: ignore[override]
        return uuid4()

    def emit_action(self, action: ActionRecord, *, metrics=None, caused_by=None) -> None:
        return None

    def emit_reflect(self, *, success: bool, reasons: list[str], metrics=None, caused_by=None) -> None:
        return None


def _config_snapshot(tmp_path: Path) -> ConfigSnapshot:
    return ConfigSnapshot.from_mapping(
        {
            "runs_dir": str(tmp_path),
            "agents": "agents.yaml",
            "tasks": "tasks.yaml",
            "timeout_sec": 60,
            "intuition_mode": "advisory",
            "direction_min_confidence": 0.5,
            "planner_mode": "minimal",
            "policy_aliases": {},
            "learn_mode": "off",
            "learn_home": str(tmp_path / "learn"),
            "learn_auto_apply_min_successes": 1,
            "learn_auto_apply_min_confidence": 0.8,
            "prompt_provenance_enabled": False,
            "prompt_provenance_mode": "hash_only",
        }
    )


def _run_episode(
    *,
    tmp_path: Path,
    workspace: Path | None,
    verify,
) -> dict[str, object]:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_test",
        seed=0,
        task="Verify workspace",
        tags={},
        adapter_label="adapter:core.minimal",
        started_at="2025-01-01T00:00:00Z",
        workspace=workspace,
        verify=verify,
    )
    state_repo = RuntimeStateRepository(context=context)
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=DummyEventBus(),
        state_repository=state_repo,
        snapshot_writer=SnapshotArtifactWriter(
            gateway=FileSystemSnapshotGateway(),
            metadata_store=FileSystemSnapshotMetadataStore(),
            clock=UtcSnapshotClock(),
            immutability_guard=ArtifactImmutabilityGuard(ManifestSealStatus()),
        ),
        file_reader_factory=lambda root: FileSystemFileReader(root=root),
    )
    runner = EpisodeRunner(deps)
    result = runner.run(EpisodeRequest(goal=context.task, beliefs=(), context=context))

    finalize_summary(
        run_dir=run_dir,
        episode_id=context.episode_id,
        task=context.task,
        seed=context.seed,
        started_at=context.started_at,
        intuition_enabled=False,
        intuition_mode=context.intuition_mode,
        using_label=context.adapter_label,
        tags=context.tags,
        intuition=None,
        schema_version=SUMMARY_SCHEMA_VERSION,
        config=_config_snapshot(tmp_path),
        ports={},
        adapter_result=result.adapter_result,
        outcome=result.verification_outcome,
        verification=result.verification,
    )
    return json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def test_summary_verification_unverified(tmp_path: Path) -> None:
    summary = _run_episode(tmp_path=tmp_path, workspace=None, verify=None)

    assert summary["adapter_result"] == "success"
    assert summary["outcome"] == "success_unverified"
    verification = summary["verification"]
    assert verification["provided"] is False
    assert verification["passed"] is None
    assert verification["snapshots"] is None
    assert verification["workspace_diff"] is None
    assert verification["policy"]["ignore"] == [".git", "__pycache__", ".venv", ".noesis"]


def test_summary_verification_success(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "config.txt").write_text("hello world", encoding="utf-8")
    verify = [FileExistsAssertion("config.txt"), FileContainsAssertion("config.txt", "hello")]

    summary = _run_episode(tmp_path=tmp_path, workspace=workspace, verify=verify)

    assert summary["adapter_result"] == "success"
    assert summary["outcome"] == "success"
    verification = summary["verification"]
    assert verification["provided"] is True
    assert verification["passed"] is True
    assert verification["snapshots"]["pre"] == "snapshots/pre.json"
    assert verification["workspace_diff"] == {"added": [], "modified": [], "deleted": []}


def test_summary_verification_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "config.txt").write_text("hello world", encoding="utf-8")
    verify = [FileContainsAssertion("config.txt", "missing")]

    summary = _run_episode(tmp_path=tmp_path, workspace=workspace, verify=verify)

    assert summary["adapter_result"] == "success"
    assert summary["outcome"] == "goal_not_achieved"
    verification = summary["verification"]
    assert verification["provided"] is True
    assert verification["passed"] is False
    assert verification["assertions"][0]["reason"] == "substring_not_found"


def test_summary_verification_workspace_missing(tmp_path: Path) -> None:
    verify = [FileExistsAssertion("config.txt")]

    summary = _run_episode(tmp_path=tmp_path, workspace=None, verify=verify)

    assert summary["adapter_result"] == "skipped"
    assert summary["outcome"] == "error"
    verification = summary["verification"]
    assert verification["provided"] is True
    assert verification["passed"] is None
    assert verification["error"] == "workspace_unavailable"
    assert verification["snapshots"] is None
