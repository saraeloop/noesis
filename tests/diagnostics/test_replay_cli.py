from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from noesis.diagnostics import compare_runs
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.interfaces.config import ConfigSnapshot, PlannerMode
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG
from noesis.runtime.session import SessionBuilder
from noesis.runtime.paths import resolve_noesis_paths
from tests.runtime.test_determinism import _FakeConfigPort


def _config_snapshot(
    root: Path,
    *,
    planner_mode: PlannerMode,
) -> ConfigSnapshot:
    learn_home = root / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    data = {
        "runs_dir": str(root),
        "agents": "agents.toml",
        "tasks": "tasks.toml",
        "timeout_sec": 5,
        "intuition_mode": IntuitionMode.ADVISORY.value,
        "direction_min_confidence": 0.5,
        "planner_mode": planner_mode.value,
        "policy_aliases": {},
        "learn_mode": LearnMode.OFF.value,
        "learn_home": str(learn_home),
        "learn_auto_apply_min_successes": 1,
        "learn_auto_apply_min_confidence": 0.5,
        "prompt_provenance_enabled": False,
        "prompt_provenance_mode": "hash_only",
    }
    return ConfigSnapshot.from_mapping(data)


def _build_session(root: Path, *, timestamp_ms: int, seed: int, planner_mode: PlannerMode) -> SessionBuilder:
    clock = DeterministicClock(
        start_at=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
        tick_ms=5.0,
    )
    rng = DeterministicRNG(seed=seed)
    snapshot = _config_snapshot(root, planner_mode=planner_mode)
    return (
        SessionBuilder(config_port=_FakeConfigPort(snapshot))
        .with_determinism(clock=clock, rng=rng, episode_timestamp_ms=timestamp_ms)
    )


def _run_veto_pair(tmp_path: Path) -> tuple[Path, Path]:
    timestamp_ms = 1_735_700_000_000
    seed = 999
    root_a = tmp_path / "veto_a"
    root_b = tmp_path / "veto_b"
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)

    session_a = _build_session(root_a, timestamp_ms=timestamp_ms, seed=seed, planner_mode=PlannerMode.META).build()
    session_b = _build_session(root_b, timestamp_ms=timestamp_ms, seed=seed, planner_mode=PlannerMode.META).build()

    task = "veto this action: delete production database"
    ep_a = session_a.run(task, intuition=False)
    ep_b = session_b.run(task, intuition=False)
    layout_a = resolve_noesis_paths(workspace=None, runs_dir=root_a)
    layout_b = resolve_noesis_paths(workspace=None, runs_dir=root_b)
    return layout_a.episodes_dir / ep_a, layout_b.episodes_dir / ep_b


def test_replay_cli_reports_no_drift_for_veto_runs(tmp_path: Path) -> None:
    run_a, run_b = _run_veto_pair(tmp_path)

    # Sanity: library compare_runs sees no drift
    result = compare_runs(run_a, run_b)
    assert not result.is_drift, f"replay drifted: {result.mismatches}"

    # CLI invocation should also report NO_DRIFT
    cmd = [
        sys.executable,
        "-m",
        "noesis.cli",
        "diagnostics",
        "replay",
        str(run_a),
        str(run_b),
        "--json",
        "--strict",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload.get("status") in {"ok", "NO_DRIFT"}, payload
