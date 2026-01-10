from __future__ import annotations

import pytest

from noesis.domain.snapshot import Snapshot


def test_snapshot_diff_added_modified_deleted_sorted() -> None:
    pre = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:00Z",
        files={
            "b.txt": "sha256:bbb",
            "a.txt": "sha256:aaa",
            "d.txt": "sha256:ddd",
        },
    )
    post = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:01Z",
        files={
            "b.txt": "sha256:bbb-changed",
            "c.txt": "sha256:ccc",
        },
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
        ),
        Snapshot(
            workspace_root="/workspace",
            captured_at="2024-01-01T00:00:01Z",
            files={"a.txt": "sha256:aaa"},
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
        files={"a.txt": "sha256:aaa"},
    )

    with pytest.raises(TypeError):
        snap.files["b.txt"] = "sha256:bbb"


def test_snapshot_to_dict_returns_mutable_files_mapping() -> None:
    snap = Snapshot(
        workspace_root="/workspace",
        captured_at="2024-01-01T00:00:00Z",
        files={"a.txt": "sha256:aaa"},
    )

    payload = snap.to_dict()

    assert type(payload["files"]) is dict
    payload["files"]["b.txt"] = "sha256:bbb"
    assert payload["files"]["b.txt"] == "sha256:bbb"
