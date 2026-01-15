from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import noesis as ns
from noesis.runtime.paths import resolve_noesis_paths


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def _write_summary(run_dir: Path, episode_id: str) -> None:
    payload = {
        "schema_version": "1.3.0",
        "episode_id": episode_id,
        "task": "legacy task",
        "started_at": "2025-01-01T00:00:00Z",
        "duration_sec": 0.1,
        "flags": {"mode": "off"},
        "metrics": {"success": 1},
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_run_writes_to_noesis_layout(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir), planner_mode="minimal", governance_mode="off")
        episode_id = ns.run("layout test", intuition=False)
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        assert (layout.episodes_dir / episode_id / "summary.json").exists()
        index_path = layout.processes_dir / "index.json"
        assert index_path.exists()
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        process_ids = index_payload.get("process_ids") or []
        assert process_ids
        for process_id in process_ids:
            assert (layout.processes_dir / f"{process_id}.json").exists()


def test_list_runs_discovers_legacy_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    legacy_run = runs_dir / "ep_legacy"
    _write_summary(legacy_run, "ep_legacy")
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))
        rows = ns.list_runs(limit=10)
    episode_ids = {row.get("episode_id") for row in rows}
    assert "ep_legacy" in episode_ids
