from __future__ import annotations

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

    assert diff.added == ["c.txt"]
    assert diff.modified == ["b.txt"]
    assert diff.deleted == ["a.txt", "d.txt"]
