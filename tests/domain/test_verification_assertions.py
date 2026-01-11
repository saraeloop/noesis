from __future__ import annotations

from pathlib import Path

from noesis.domain.snapshot import DEFAULT_IGNORE, Snapshot, SnapshotPolicy, WorkspaceDiff
from noesis.domain.verification import (
    AssertionContext,
    FileContainsAssertion,
    FileExistsAssertion,
    NoModificationsAssertion,
    OnlyModifiedAssertion,
)


class FakeReader:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def read_text(self, path: str) -> str:
        if path not in self._mapping:
            raise FileNotFoundError(path)
        return self._mapping[path]


def _snapshot(files: dict[str, str]) -> Snapshot:
    return Snapshot(
        workspace_root="/workspace",
        files=files,
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
    )


def test_file_exists_uses_snapshot() -> None:
    context = AssertionContext(snapshot=_snapshot({"a.txt": "hash"}))
    result = FileExistsAssertion("a.txt").evaluate(context)

    assert result.passed is True
    assert result.target == "a.txt"


def test_file_exists_fails_without_snapshot() -> None:
    result = FileExistsAssertion("missing.txt").evaluate(AssertionContext())

    assert result.passed is False
    assert result.reason == "snapshot_unavailable"


def test_file_exists_normalizes_path() -> None:
    context = AssertionContext(snapshot=_snapshot({"dir/file.txt": "hash"}))
    result = FileExistsAssertion(Path("dir") / "file.txt").evaluate(context)

    assert result.passed is True
    assert result.target == "dir/file.txt"


def test_file_contains_reads_from_reader() -> None:
    reader = FakeReader({"config.yaml": "hello world"})
    context = AssertionContext(file_reader=reader)
    result = FileContainsAssertion("config.yaml", "world").evaluate(context)

    assert result.passed is True


def test_file_contains_fails_when_missing() -> None:
    reader = FakeReader({})
    context = AssertionContext(file_reader=reader)
    result = FileContainsAssertion("config.yaml", "world").evaluate(context)

    assert result.passed is False
    assert result.reason == "file_not_found: config.yaml"


def test_only_modified_passes_when_subset() -> None:
    diff = WorkspaceDiff(added=(), modified=("a.txt",), deleted=())
    context = AssertionContext(diff=diff)
    result = OnlyModifiedAssertion(["a.txt", "b.txt"]).evaluate(context)

    assert result.passed is True


def test_only_modified_fails_on_added_or_deleted() -> None:
    diff = WorkspaceDiff(added=("new.txt",), modified=(), deleted=())
    context = AssertionContext(diff=diff)
    result = OnlyModifiedAssertion(["a.txt"]).evaluate(context)

    assert result.passed is False
    assert "added=" in (result.reason or "")


def test_no_modifications_passes_when_clean() -> None:
    diff = WorkspaceDiff()
    context = AssertionContext(diff=diff)
    result = NoModificationsAssertion().evaluate(context)

    assert result.passed is True


def test_no_modifications_fails_when_changes_present() -> None:
    diff = WorkspaceDiff(modified=("a.txt",))
    context = AssertionContext(diff=diff)
    result = NoModificationsAssertion().evaluate(context)

    assert result.passed is False
    assert "modified=" in (result.reason or "")
