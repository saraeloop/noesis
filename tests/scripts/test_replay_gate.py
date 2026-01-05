from pathlib import Path

import pytest

from scripts import replay_gate


def _make_dir(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir()
    return path


def test_episode_dir_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="fixture_hygiene"):
        replay_gate._episode_dir(tmp_path)


def test_episode_dir_returns_single_match(tmp_path: Path) -> None:
    expected = _make_dir(tmp_path, "ep_one")
    _make_dir(tmp_path, "learn")
    assert replay_gate._episode_dir(tmp_path) == expected


def test_episode_dir_multiple_matches_raises(tmp_path: Path) -> None:
    _make_dir(tmp_path, "ep_a")
    _make_dir(tmp_path, "ep_b")
    _make_dir(tmp_path, "learn")
    with pytest.raises(ValueError) as excinfo:
        replay_gate._episode_dir(tmp_path)
    message = str(excinfo.value)
    assert "fixture_hygiene" in message
    assert "ep_a" in message
    assert "ep_b" in message
    assert "learn" in message
