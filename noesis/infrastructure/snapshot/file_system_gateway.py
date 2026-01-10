"""Filesystem-backed snapshot capture and persistence."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Iterable, Sequence

from noesis.domain.snapshot import DEFAULT_IGNORE, HASH_PREFIX, Snapshot, SnapshotCaptureError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _has_ignored_segment(relative_path: Path, ignore: Sequence[str]) -> bool:
    return any(segment in ignore for segment in relative_path.parts)


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return f"{HASH_PREFIX}{hasher.hexdigest()}"


def _iter_files(workspace: Path, ignore: Sequence[str]) -> Iterable[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for root, dirs, files in os.walk(workspace, followlinks=False):
        root_path = Path(root)
        relative_root = root_path.relative_to(workspace)
        if relative_root.parts and _has_ignored_segment(relative_root, ignore):
            dirs[:] = []
            continue
        dirs[:] = [
            name
            for name in dirs
            if not _has_ignored_segment((relative_root / name), ignore)
            and not (root_path / name).is_symlink()
        ]
        for name in files:
            path = root_path / name
            if path.is_symlink():
                continue
            relative_path = path.relative_to(workspace)
            if _has_ignored_segment(relative_path, ignore):
                continue
            entries.append((relative_path.as_posix(), path))
    entries.sort(key=lambda item: item[0])
    return entries


@dataclass(slots=True)
class FileSystemSnapshotGateway:
    """Capture and persist workspace snapshots on the local filesystem."""

    now: Callable[[], datetime] = field(default=_utc_now)

    def capture(self, workspace: Path, ignore: Sequence[str] = DEFAULT_IGNORE) -> Snapshot:
        try:
            files = {
                rel_path: _hash_file(path) for rel_path, path in _iter_files(workspace, ignore)
            }
        except OSError as exc:
            raise SnapshotCaptureError(f"snapshot_capture_failed: {exc}") from exc
        captured_at = self.now().isoformat()
        return Snapshot(
            workspace_root=workspace.resolve().as_posix(),
            captured_at=captured_at,
            files=files,
        )

    def save(self, snapshot: Snapshot, path: Path) -> None:
        payload = json.dumps(
            snapshot.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        path.write_text(payload, encoding="utf-8")

    def load(self, path: Path) -> Snapshot:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Snapshot.from_dict(data)


__all__ = ["FileSystemSnapshotGateway"]
