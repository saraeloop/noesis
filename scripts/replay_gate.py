"""
Determinism replay gate for CI.

Checks:
- Minimal-mode golden pair under tests/golden/deterministic_run.
- Deterministic veto scenario generated on the fly in planner META mode.

Fails with non-zero exit when drift is detected.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from noesis.diagnostics import compare_runs
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG
from noesis.runtime.session import SessionBuilder


def _episode_dir(root: Path) -> Path:
    candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("ep_"))
    if not candidates:
        raise FileNotFoundError(f"No episode directories found under {root}")
    return candidates[0]


def _assert_no_drift(label: str, a: Path, b: Path) -> None:
    result = compare_runs(a, b)
    if result.is_drift:
        mismatches = "; ".join(f"{m.artifact}: {m.detail}" for m in result.mismatches)
        raise SystemExit(f"[{label}] drift detected: {mismatches}")
    print(f"[{label}] OK (NO_DRIFT)")


@dataclass(slots=True)
class _SnapshotPort(ConfigPort):
    snapshot: ConfigSnapshot

    def get(self) -> ConfigSnapshot:  # type: ignore[override]
        return self.snapshot

    def set(self, **overrides: object) -> ConfigSnapshot:  # type: ignore[override]
        data = self.snapshot.to_mapping()
        data.update(overrides)
        self.snapshot = ConfigSnapshot.from_mapping(data)
        return self.snapshot

    def reload(self) -> ConfigSnapshot:  # type: ignore[override]
        return self.snapshot

    def supports(self, capability: str) -> bool:  # type: ignore[override]
        return False


def _config_snapshot(root: Path, planner_mode: PlannerMode) -> ConfigSnapshot:
    learn_home = root / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
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


def _build_session(root: Path, *, ts_ms: int, seed: int, planner_mode: PlannerMode):
    clock = DeterministicClock(
        start_at=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
        tick_ms=5.0,
    )
    rng = DeterministicRNG(seed=seed)
    snapshot = _config_snapshot(root, planner_mode)
    port = _SnapshotPort(snapshot)
    builder = SessionBuilder(config_port=port).with_determinism(
        clock=clock,
        rng=rng,
        episode_timestamp_ms=ts_ms,
    )
    return builder.build()


def _check_minimal_golden() -> None:
    base = Path("tests/golden/deterministic_run")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")
    _assert_no_drift("minimal-golden", run_a, run_b)


def _check_veto_generated(tmp: Path) -> None:
    ts_ms = 1_735_700_000_000
    seed = 999
    root_a = tmp / "veto_a"
    root_b = tmp / "veto_b"
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)

    session_a = _build_session(root_a, ts_ms=ts_ms, seed=seed, planner_mode=PlannerMode.META)
    session_b = _build_session(root_b, ts_ms=ts_ms, seed=seed, planner_mode=PlannerMode.META)

    task = "veto this action: delete production database"
    ep_a = session_a.run(task, intuition=False)
    ep_b = session_b.run(task, intuition=False)

    _assert_no_drift("veto-generated", root_a / ep_a, root_b / ep_b)


def main() -> int:
    try:
        _check_minimal_golden()
        tmp = Path("artifacts/replay_tmp")
        tmp.mkdir(parents=True, exist_ok=True)
        _check_veto_generated(tmp)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
