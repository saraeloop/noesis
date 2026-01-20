"""Filesystem persistence for snapshot capture timestamps."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from noesis.domain.verification import SnapshotCaptureTimes


@dataclass(slots=True)
class FileSystemSnapshotMetadataStore:
    """Persist snapshot capture metadata in the snapshots directory."""

    filename: str = "metadata.json"

    def path_for(self, *, snapshots_dir: Path) -> Path:
        return snapshots_dir / self.filename

    def save(self, *, snapshots_dir: Path, times: SnapshotCaptureTimes) -> Path:
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"snapshot_captured_at": times.to_dict()},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        path = self.path_for(snapshots_dir=snapshots_dir)
        path.write_text(payload, encoding="utf-8")
        return path

    def load(self, *, snapshots_dir: Path) -> SnapshotCaptureTimes | None:
        path = self.path_for(snapshots_dir=snapshots_dir)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Snapshot metadata must be a JSON object.")
        payload = data.get("snapshot_captured_at", {})
        if not isinstance(payload, dict):
            raise ValueError("Snapshot metadata snapshot_captured_at must be an object.")
        return SnapshotCaptureTimes.from_dict(payload)


__all__ = ["FileSystemSnapshotMetadataStore"]
