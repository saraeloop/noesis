"""
Workspace snapshot domain models and contracts.

Architecture mapping:
- Entities: Snapshot, WorkspaceDiff
- Use Cases: SnapshotWorkspace (noesis/usecases/snapshot_workspace.py)
- Interface Adapters: SnapshotGateway implementations
- Infrastructure: FileSystemSnapshotGateway (noesis/infrastructure/snapshot/file_system_gateway.py)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

DEFAULT_IGNORE: tuple[str, ...] = (".git", "__pycache__", ".venv", ".noesis")
HASH_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class WorkspaceDiff:
    """Deterministic diff between two workspace snapshots."""

    added: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "added", tuple(self.added))
        object.__setattr__(self, "modified", tuple(self.modified))
        object.__setattr__(self, "deleted", tuple(self.deleted))


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Immutable view of workspace files and their hashes."""

    workspace_root: str
    captured_at: str
    files: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping with stable ordering."""
        return {
            "workspace_root": self.workspace_root,
            "captured_at": self.captured_at,
            "files": _sorted_mapping(self.files),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Snapshot":
        """Hydrate a snapshot from a JSON mapping."""
        workspace_root = data.get("workspace_root")
        captured_at = data.get("captured_at")
        files = data.get("files")
        if not isinstance(workspace_root, str) or not isinstance(captured_at, str):
            raise ValueError("Snapshot mapping missing required string fields.")
        if not isinstance(files, Mapping):
            raise ValueError("Snapshot mapping missing files mapping.")
        return cls(
            workspace_root=workspace_root,
            captured_at=captured_at,
            files={str(key): str(value) for key, value in files.items()},
        )

    @staticmethod
    def diff(pre: "Snapshot", post: "Snapshot") -> WorkspaceDiff:
        """Return deterministic added/modified/deleted paths."""
        pre_paths = set(pre.files.keys())
        post_paths = set(post.files.keys())

        added = sorted(post_paths - pre_paths)
        deleted = sorted(pre_paths - post_paths)
        modified = sorted(
            path for path in (pre_paths & post_paths) if pre.files[path] != post.files[path]
        )
        return WorkspaceDiff(added=tuple(added), modified=tuple(modified), deleted=tuple(deleted))


class SnapshotGateway(Protocol):
    """Boundary for capturing and persisting workspace snapshots."""

    def capture(self, workspace: Path, ignore: Sequence[str] = DEFAULT_IGNORE) -> Snapshot:
        ...

    def save(self, snapshot: Snapshot, path: Path) -> None:
        ...

    def load(self, path: Path) -> Snapshot:
        ...


class SnapshotCaptureError(RuntimeError):
    """Raised when a snapshot capture fails due to IO issues."""


def _sorted_mapping(data: Mapping[str, str]) -> dict[str, str]:
    return {key: data[key] for key in sorted(data)}


__all__ = [
    "DEFAULT_IGNORE",
    "HASH_PREFIX",
    "Snapshot",
    "SnapshotCaptureError",
    "SnapshotGateway",
    "WorkspaceDiff",
]
