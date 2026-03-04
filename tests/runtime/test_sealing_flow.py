from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

import pytest

import noesis as ns
import noesis.core as core
from noesis.domain.artifacts.immutability import ImmutabilityError
from noesis.domain.artifacts.finalization import FinalizationRecord
from noesis.runtime.artifacts.ids import EpisodeIds
from noesis.runtime.artifacts.immutability import default_artifact_guard
from noesis.runtime.paths import resolve_noesis_paths
from noesis.domain.artifacts.finalization import FINAL_FILE_NAME
from noesis.usecases.finalization import FinalizationWriter


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def test_seal_failure_rolls_back_final_marker_and_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir = tmp_path / "runs"

    def _boom(*_args, **_kwargs):
        raise RuntimeError("manifest write failed")

    monkeypatch.setattr(core.ManifestWriter, "finalize", _boom)

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        with pytest.raises(RuntimeError, match="manifest write failed"):
            ns.run("seal rollback test", intuition=False)
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)

    episodes = sorted(path for path in layout.episodes_dir.iterdir() if path.is_dir() and path.name.startswith("ep_"))
    assert episodes, "expected a run directory to be created"
    latest = episodes[-1]
    assert not (latest / FINAL_FILE_NAME).exists(), "final marker must be removed when seal fails"
    assert not (latest / "manifest.json").exists(), "manifest must not exist when seal fails"


def test_double_seal_fails_explicitly_without_mutation(tmp_path: Path) -> None:
    run_dir = tmp_path / "ep_double_seal"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    (run_dir / "state.json").write_text('{"ok": true}\n', encoding="utf-8")
    (run_dir / "events.jsonl").write_text('{"event":"start"}\n', encoding="utf-8")

    ctx = core._EpCtx(
        ids=EpisodeIds.from_episode("ep_double_seal"),
        run_dir=run_dir,
        started_at="2025-01-01T00:00:00Z",
    )
    final_writer = FinalizationWriter(immutability_guard=default_artifact_guard())
    record = FinalizationRecord(
        episode_id="ep_double_seal",
        process_id="proc_test",
        run_index=1,
        finalized_at="2025-01-01T00:00:00Z",
        outcome="success",
        verification_status="unverified",
    )

    manifest_path, _ = core._seal_episode(ctx=ctx, final_writer=final_writer, final_record=record)
    manifest_before = manifest_path.read_bytes()
    manifest_hash_before = hashlib.sha256(manifest_before).hexdigest()
    final_before = (run_dir / FINAL_FILE_NAME).read_text(encoding="utf-8")

    with pytest.raises(ImmutabilityError, match="finalization marker already exists"):
        core._seal_episode(ctx=ctx, final_writer=final_writer, final_record=record)

    manifest_after = manifest_path.read_bytes()
    manifest_hash_after = hashlib.sha256(manifest_after).hexdigest()
    assert manifest_hash_after == manifest_hash_before
    assert (run_dir / FINAL_FILE_NAME).read_text(encoding="utf-8") == final_before

    manifest_payload = json.loads(manifest_after.decode("utf-8"))
    assert any(item.get("name") == FINAL_FILE_NAME for item in manifest_payload.get("files", []))


def test_enforce_veto_maps_to_final_v2_contract(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs-veto-final"

    class NoopGraph:
        def invoke(self, payload):
            return payload

    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), governance_mode="enforce")
        episode_id = ns.solve(
            task="Danger operation: delete production database",
            using=lambda: NoopGraph(),
            intuition=False,
        )
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)

    final_path = layout.episodes_dir / episode_id / FINAL_FILE_NAME
    final_payload = json.loads(final_path.read_text(encoding="utf-8"))
    assert final_payload["schema_version"] == "final/2.0.0"
    assert final_payload["outcome"] == "vetoed"
    assert final_payload["verification_status"] == "not_applicable"
