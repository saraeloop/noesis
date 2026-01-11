"""Use cases for snapshot artifacts and capture timestamps."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from noesis.domain.snapshot import DEFAULT_IGNORE, Snapshot, SnapshotGateway
from noesis.domain.verification import (
    SnapshotCaptureTimes,
    SnapshotClock,
    SnapshotMetadataStore,
)


@dataclass(slots=True)
class SnapshotArtifactWriter:
    """
    Capture snapshot artifacts and record capture timestamps.

    Integration note:
    EpisodeRunner will call capture_and_store() for "pre" and "post" phases,
    then merge snapshot_captured_at into summary.json verification once wired.
    """

    gateway: SnapshotGateway
    metadata_store: SnapshotMetadataStore
    clock: SnapshotClock

    def capture_and_store(
        self,
        *,
        phase: Literal["pre", "post"],
        workspace: Path,
        run_dir: Path,
        ignore: Sequence[str] = DEFAULT_IGNORE,
    ) -> Snapshot:
        snapshot = self.gateway.capture(workspace=workspace, ignore=ignore)
        snapshots_dir = run_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshots_dir / f"{phase}.json"
        self.gateway.save(snapshot, snapshot_path)

        # Capture completed time to align timestamps with persisted artifacts.
        timestamp = self.clock.now_utc_iso()
        times = self.metadata_store.load(snapshots_dir=snapshots_dir) or SnapshotCaptureTimes()
        if phase == "pre":
            times = times.with_pre(timestamp)
        else:
            times = times.with_post(timestamp)
        self.metadata_store.save(snapshots_dir=snapshots_dir, times=times)
        return snapshot


__all__ = ["SnapshotArtifactWriter", "SnapshotClock", "SnapshotMetadataStore"]
