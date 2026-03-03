from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path

import noesis as ns
from noesis.runtime.paths import resolve_noesis_paths
from noesis.domain.artifacts.finalization import FINAL_FILE_NAME


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def test_episodes_dir_contains_only_episode_bundles(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        episode_id = ns.run("layout index test", intuition=False)
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)

    episodes_dir = layout.episodes_dir
    assert (episodes_dir / episode_id).is_dir()
    assert (episodes_dir / episode_id / FINAL_FILE_NAME).exists()
    manifest = json.loads((episodes_dir / episode_id / "manifest.json").read_text(encoding="utf-8"))
    assert any(item.get("name") == FINAL_FILE_NAME for item in manifest.get("files", []))

    for entry in episodes_dir.iterdir():
        assert entry.is_dir()
        assert entry.name.startswith("ep_")

    assert not (episodes_dir / "_episodes").exists()
