from __future__ import annotations

import os
from pathlib import Path

import pytest

from noesis.domain.snapshot import DEFAULT_IGNORE, SnapshotCaptureError
from noesis.infrastructure.snapshot.file_system_gateway import FileSystemSnapshotGateway


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_capture_is_deterministic_for_files_mapping(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_text(workspace / "a.txt", "alpha")
    _write_text(workspace / "dir" / "b.txt", "bravo")

    gateway = FileSystemSnapshotGateway()
    first = gateway.capture(workspace)
    second = gateway.capture(workspace)

    assert first.files == second.files


def test_capture_ignores_segment_tokens(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_text(workspace / "keep.txt", "ok")
    _write_text(workspace / ".git" / "config", "ignored")
    _write_text(workspace / "__pycache__" / "skip.txt", "ignored")
    _write_text(workspace / ".venv" / "skip.txt", "ignored")
    _write_text(workspace / ".noesis" / "skip.txt", "ignored")
    _write_text(workspace / "__init__" / "keep.txt", "ok")

    gateway = FileSystemSnapshotGateway()
    snapshot = gateway.capture(workspace)

    assert list(snapshot.files.keys()) == ["__init__/keep.txt", "keep.txt"]
    assert list(snapshot.files.keys()) == sorted(snapshot.files.keys())


def test_capture_skips_symlinks(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("data", encoding="utf-8")
    link = workspace / "link.txt"

    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    gateway = FileSystemSnapshotGateway()
    snapshot = gateway.capture(workspace)

    assert "link.txt" not in snapshot.files
    assert "target.txt" in snapshot.files


def test_capture_skips_symlinked_directories(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    _write_text(real_dir / "outside.txt", "outside")
    link_dir = workspace / "linked"

    try:
        os.symlink(real_dir, link_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    gateway = FileSystemSnapshotGateway()
    snapshot = gateway.capture(workspace)

    assert "linked/outside.txt" not in snapshot.files


def test_capture_ignores_segments_with_symlinked_children(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    _write_text(real_dir / "outside.txt", "outside")
    ignored_dir = workspace / ".git"
    ignored_dir.mkdir()
    link_dir = ignored_dir / "linked"

    try:
        os.symlink(real_dir, link_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    gateway = FileSystemSnapshotGateway()
    snapshot = gateway.capture(workspace)

    assert "linked/outside.txt" not in snapshot.files


def test_save_and_load_snapshot_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_text(workspace / "a.txt", "alpha")

    gateway = FileSystemSnapshotGateway()
    snapshot = gateway.capture(workspace)
    path = tmp_path / "snapshot.json"

    gateway.save(snapshot, path)
    loaded = gateway.load(path)

    assert snapshot.files == loaded.files
    assert snapshot.workspace_root == loaded.workspace_root
    assert loaded.policy.ignore == DEFAULT_IGNORE
    assert loaded.policy.symlinks == "skip"


def test_capture_raises_snapshot_capture_error_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_text(workspace / "a.txt", "alpha")

    gateway = FileSystemSnapshotGateway()

    def _raise_oserror(_: Path, __: int = 0) -> str:
        raise OSError("nope")

    monkeypatch.setattr(
        "noesis.infrastructure.snapshot.file_system_gateway._hash_file",
        _raise_oserror,
    )

    with pytest.raises(SnapshotCaptureError):
        gateway.capture(workspace)
