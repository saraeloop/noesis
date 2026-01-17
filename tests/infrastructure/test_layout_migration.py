from __future__ import annotations

import json
from pathlib import Path

from noesis.infrastructure.layout_migration import migrate_layout
from noesis.runtime.paths import resolve_noesis_paths


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


def test_migrate_layout_copies_legacy_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    legacy_run = runs_dir / "ep_legacy"
    _write_summary(legacy_run, "ep_legacy")

    legacy_processes = runs_dir / "processes"
    legacy_processes.mkdir(parents=True, exist_ok=True)
    (legacy_processes / "proc_1.json").write_text(
        json.dumps(
            {
                "process_id": "proc_1",
                "process_name": "proc",
                "kind": "oneshot",
                "status": "idle",
                "created_at": "2025-01-01T00:00:00Z",
                "last_seen_at": "2025-01-01T00:00:00Z",
                "active_run_id": None,
                "last_run_outcome": None,
                "run_index": 0,
            }
        )
    )

    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    result = migrate_layout(layout)

    assert result.episodes_copied == 1
    assert result.processes_copied == 1
    assert (layout.episodes_dir / "ep_legacy").exists()
    assert (layout.processes_dir / "proc_1.json").exists()
    assert (layout.root / "MIGRATED_FROM.json").exists()
