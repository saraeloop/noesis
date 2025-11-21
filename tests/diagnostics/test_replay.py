from __future__ import annotations

import shutil
from pathlib import Path

from noesis.diagnostics import compare_runs


def _episode_dir(root: Path) -> Path:
    candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("ep_"))
    assert candidates, f"no episode directories found under {root}"
    return candidates[0]


def test_compare_runs_reports_no_drift() -> None:
    base = Path("tests/golden/deterministic_run")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")

    result = compare_runs(run_a, run_b)

    assert not result.is_drift
    assert result.status == "NO_DRIFT"
    assert result.mismatches == []


def test_compare_runs_surfaces_byte_drift(tmp_path: Path) -> None:
    base = Path("tests/golden/deterministic_run")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")

    # Copy run_b and introduce a small drift in summary.json
    modified = tmp_path / run_b.name
    shutil.copytree(run_b, modified)
    summary_path = modified / "summary.json"
    summary_path.write_text(summary_path.read_text() + " ")  # trailing space changes bytes

    result = compare_runs(run_a, modified)

    assert result.is_drift
    assert any(m.artifact == "summary.json" for m in result.mismatches)
