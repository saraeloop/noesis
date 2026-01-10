from __future__ import annotations

import pytest

from noesis.domain.snapshot import DEFAULT_IGNORE, Snapshot, SnapshotPolicy


def test_snapshot_diff_added_modified_deleted_sorted() -> None:
    pre = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:00Z",
        files={
            "b.txt": "bbb",
            "a.txt": "aaa",
            "d.txt": "ddd",
        },
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
    )
    post = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:01Z",
        files={
            "b.txt": "bbb-changed",
            "c.txt": "ccc",
        },
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
    )

    diff = Snapshot.diff(pre, post)

    assert diff.added == ("c.txt",)
    assert diff.modified == ("b.txt",)
    assert diff.deleted == ("a.txt", "d.txt")


def test_workspace_diff_is_immutable() -> None:
    diff = Snapshot.diff(
        Snapshot(
            workspace_root="/workspace",
            captured_at="2024-01-01T00:00:00Z",
            files={},
            policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
        ),
        Snapshot(
            workspace_root="/workspace",
            captured_at="2024-01-01T00:00:01Z",
            files={"a.txt": "aaa"},
            policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
        ),
    )

    with pytest.raises(AttributeError):
        diff.added = ("override.txt",)

    with pytest.raises(TypeError):
        diff.added[0] = "override.txt"


def test_snapshot_files_is_read_only_mapping() -> None:
    snap = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:00Z",
        files={"a.txt": "aaa"},
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
    )

    with pytest.raises(TypeError):
        snap.files["b.txt"] = "sha256:bbb"


def test_snapshot_to_dict_returns_mutable_files_mapping() -> None:
    snap = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:00Z",
        files={"a.txt": "aaa"},
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE),
    )

    payload = snap.to_dict()

    assert type(payload["files"]) is dict
    assert "captured_at" not in payload
    assert payload["policy"]["ignore"] == list(DEFAULT_IGNORE)
    payload["files"]["b.txt"] = "bbb"
    assert payload["files"]["b.txt"] == "bbb"
