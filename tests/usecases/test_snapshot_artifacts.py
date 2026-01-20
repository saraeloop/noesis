from __future__ import annotations

import json
from pathlib import Path

from noesis.infrastructure.snapshot.clock import UtcSnapshotClock
from noesis.infrastructure.snapshot.file_system_gateway import FileSystemSnapshotGateway
from noesis.infrastructure.snapshot.metadata_store import FileSystemSnapshotMetadataStore
from noesis.infrastructure.immutability import ManifestSealStatus
from noesis.usecases.immutability import ArtifactImmutabilityGuard
from noesis.usecases.snapshot_artifacts import SnapshotArtifactWriter, SnapshotClock


class FixedSnapshotClock:
    def __init__(self, values: list[str]) -> None:
        self._values = values
        self._index = 0

    def now_utc_iso(self) -> str:
        value = self._values[self._index]
        self._index += 1
        return value


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_snapshot_artifact_writer_records_capture_times(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_text(workspace / "a.txt", "alpha")

    run_dir = tmp_path / "run"
    clock: SnapshotClock = FixedSnapshotClock(
        ["2025-01-01T00:00:00+00:00", "2025-01-01T00:00:01+00:00"]
    )
    writer = SnapshotArtifactWriter(
        gateway=FileSystemSnapshotGateway(),
        metadata_store=FileSystemSnapshotMetadataStore(),
        clock=clock,
        immutability_guard=ArtifactImmutabilityGuard(ManifestSealStatus()),
    )

    writer.capture_and_store(phase="pre", workspace=workspace, run_dir=run_dir)
    writer.capture_and_store(phase="post", workspace=workspace, run_dir=run_dir)

    snapshots_dir = run_dir / "snapshots"
    metadata = json.loads((snapshots_dir / "metadata.json").read_text(encoding="utf-8"))
    assert set(metadata.keys()) == {"snapshot_captured_at"}
    assert metadata["snapshot_captured_at"]["pre"] == "2025-01-01T00:00:00+00:00"
    assert metadata["snapshot_captured_at"]["post"] == "2025-01-01T00:00:01+00:00"

    pre_payload = json.loads((snapshots_dir / "pre.json").read_text(encoding="utf-8"))
    post_payload = json.loads((snapshots_dir / "post.json").read_text(encoding="utf-8"))
    assert "captured_at" not in pre_payload
    assert "captured_at" not in post_payload


def test_snapshot_clock_returns_iso_utc() -> None:
    clock = UtcSnapshotClock()
    value = clock.now_utc_iso()
    assert value.endswith("+00:00")
