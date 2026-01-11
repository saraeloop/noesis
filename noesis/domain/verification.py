"""
Domain models for verification metadata and assertions.

These entities represent audit metadata and pure verification contracts
without performing any direct I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Protocol, Sequence

from noesis.domain.snapshot import Snapshot, SnapshotPolicy, WorkspaceDiff


@dataclass(frozen=True, slots=True)
class SnapshotCaptureTimes:
    """Capture timestamps for snapshot phases."""

    pre: str | None = None
    post: str | None = None

    def with_pre(self, timestamp: str) -> "SnapshotCaptureTimes":
        return SnapshotCaptureTimes(pre=timestamp, post=self.post)

    def with_post(self, timestamp: str) -> "SnapshotCaptureTimes":
        return SnapshotCaptureTimes(pre=self.pre, post=timestamp)

    def to_dict(self) -> dict[str, str | None]:
        return {"pre": self.pre, "post": self.post}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SnapshotCaptureTimes":
        pre = data.get("pre")
        post = data.get("post")
        if pre is not None and not isinstance(pre, str):
            raise ValueError("SnapshotCaptureTimes.pre must be a string or null.")
        if post is not None and not isinstance(post, str):
            raise ValueError("SnapshotCaptureTimes.post must be a string or null.")
        return cls(pre=pre, post=post)


class SnapshotClock(Protocol):
    """Clock boundary for snapshot capture timestamps."""

    def now_utc_iso(self) -> str:
        ...


class SnapshotMetadataStore(Protocol):
    """Persistence boundary for snapshot capture timestamps."""

    def save(self, *, snapshots_dir: Path, times: SnapshotCaptureTimes) -> Path:
        ...

    def load(self, *, snapshots_dir: Path) -> SnapshotCaptureTimes | None:
        ...


@dataclass(frozen=True, slots=True)
class SnapshotPaths:
    """Snapshot artifact paths persisted during verification."""

    pre: str | None = None
    post: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"pre": self.pre, "post": self.post}


class FileContentReader(Protocol):
    """Read file contents for verification without binding to an IO layer."""

    def read_text(self, path: str) -> str:
        ...


@dataclass(frozen=True, slots=True)
class AssertionContext:
    """Context required to evaluate verification assertions."""

    snapshot: Snapshot | None = None
    diff: WorkspaceDiff | None = None
    file_reader: FileContentReader | None = None


@dataclass(frozen=True, slots=True)
class AssertionResult:
    """Result of a single assertion evaluation."""

    name: str
    target: str | tuple[str, ...] | None
    passed: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, object | None]:
        target: object | None = self.target
        if isinstance(self.target, tuple):
            target = list(self.target)
        return {
            "name": self.name,
            "target": target,
            "passed": self.passed,
            "reason": self.reason,
        }


class Assertion(Protocol):
    """Contract for deterministic verification assertions."""

    name: str

    def evaluate(self, context: AssertionContext) -> AssertionResult:
        ...


@dataclass(frozen=True, slots=True)
class FileExistsAssertion:
    """Assert that a file path exists in the captured snapshot."""

    path: str | Path
    name: str = "file_exists"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _normalize_path(self.path))

    def evaluate(self, context: AssertionContext) -> AssertionResult:
        if context.snapshot is None:
            return AssertionResult(self.name, self.path, False, "snapshot_unavailable")
        if self.path in context.snapshot.files:
            return AssertionResult(self.name, self.path, True, None)
        return AssertionResult(self.name, self.path, False, f"file_not_found: {self.path}")


@dataclass(frozen=True, slots=True)
class FileContainsAssertion:
    """Assert that a file's contents include a given substring."""

    path: str | Path
    content: str
    name: str = "file_contains"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _normalize_path(self.path))

    def evaluate(self, context: AssertionContext) -> AssertionResult:
        if context.file_reader is None:
            return AssertionResult(self.name, self.path, False, "file_reader_unavailable")
        try:
            text = context.file_reader.read_text(self.path)
        except FileNotFoundError:
            return AssertionResult(self.name, self.path, False, f"file_not_found: {self.path}")
        except OSError as exc:
            return AssertionResult(self.name, self.path, False, f"file_read_error: {exc}")
        if self.content in text:
            return AssertionResult(self.name, self.path, True, None)
        return AssertionResult(self.name, self.path, False, "substring_not_found")


@dataclass(frozen=True, slots=True)
class OnlyModifiedAssertion:
    """Assert that only the specified paths were modified and nothing added/deleted."""

    paths: Sequence[str | Path]
    name: str = "only_modified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", _normalize_paths(self.paths))

    def evaluate(self, context: AssertionContext) -> AssertionResult:
        if context.diff is None:
            return AssertionResult(self.name, self.paths, False, "diff_unavailable")
        allowed = set(self.paths)
        added = tuple(context.diff.added)
        deleted = tuple(context.diff.deleted)
        modified = tuple(path for path in context.diff.modified if path not in allowed)
        if not added and not deleted and not modified:
            return AssertionResult(self.name, self.paths, True, None)
        reason = _format_unexpected_changes(added=added, deleted=deleted, modified=modified)
        return AssertionResult(self.name, self.paths, False, reason)


@dataclass(frozen=True, slots=True)
class NoModificationsAssertion:
    """Assert that no files were added, modified, or deleted."""

    name: str = "no_modifications"

    def evaluate(self, context: AssertionContext) -> AssertionResult:
        if context.diff is None:
            return AssertionResult(self.name, None, False, "diff_unavailable")
        if not context.diff.added and not context.diff.modified and not context.diff.deleted:
            return AssertionResult(self.name, None, True, None)
        reason = _format_unexpected_changes(
            added=context.diff.added,
            deleted=context.diff.deleted,
            modified=context.diff.modified,
        )
        return AssertionResult(self.name, None, False, reason)


@dataclass(frozen=True, slots=True)
class VerificationSummary:
    """Summary of verification inputs and outcomes for an episode."""

    provided: bool
    passed: bool | None
    assertions: tuple[AssertionResult, ...] = field(default_factory=tuple)
    workspace_diff: WorkspaceDiff | None = None
    snapshots: SnapshotPaths | None = None
    policy: SnapshotPolicy = field(default_factory=SnapshotPolicy)
    error: str | None = None

    def to_dict(self) -> dict[str, object | None]:
        return {
            "provided": self.provided,
            "passed": self.passed,
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "workspace_diff": _diff_payload(self.workspace_diff),
            "snapshots": self.snapshots.to_dict() if self.snapshots else None,
            "policy": self.policy.to_dict(),
            "error": self.error,
        }


def _normalize_path(path: str | Path) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path)


def _normalize_paths(paths: Sequence[str | Path]) -> tuple[str, ...]:
    normalized = sorted({_normalize_path(path) for path in paths})
    return tuple(normalized)


def _format_unexpected_changes(
    *,
    added: Iterable[str],
    deleted: Iterable[str],
    modified: Iterable[str],
) -> str:
    parts = []
    added_list = sorted(set(added))
    deleted_list = sorted(set(deleted))
    modified_list = sorted(set(modified))
    if added_list:
        parts.append(f"added={added_list}")
    if deleted_list:
        parts.append(f"deleted={deleted_list}")
    if modified_list:
        parts.append(f"modified={modified_list}")
    return "unexpected_changes: " + ", ".join(parts)


def _diff_payload(diff: WorkspaceDiff | None) -> dict[str, list[str]] | None:
    if diff is None:
        return None
    return {
        "added": list(diff.added),
        "modified": list(diff.modified),
        "deleted": list(diff.deleted),
    }


__all__ = [
    "Assertion",
    "AssertionContext",
    "AssertionResult",
    "FileContainsAssertion",
    "FileContentReader",
    "FileExistsAssertion",
    "NoModificationsAssertion",
    "OnlyModifiedAssertion",
    "SnapshotClock",
    "SnapshotCaptureTimes",
    "SnapshotMetadataStore",
    "SnapshotPaths",
    "VerificationSummary",
]
