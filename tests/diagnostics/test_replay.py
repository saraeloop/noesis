from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from noesis.artifacts import verify_manifest
from noesis.diagnostics import compare_runs


def _episode_dir(root: Path) -> Path:
    candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("ep_"))
    assert candidates, f"no episode directories found under {root}"
    return candidates[0]


@pytest.mark.parametrize(
    "dataset",
    [
        Path("tests/golden/deterministic_run"),
        Path("tests/golden/veto_enforce"),
        Path("tests/golden/adr_008/allow_enforce"),
        Path("tests/golden/adr_008/veto_enforce"),
        Path("tests/golden/adr_008/fail_closed_error"),
        Path("tests/golden/adr_008/audit_veto"),
    ],
)
def test_compare_runs_reports_no_drift(dataset: Path) -> None:
    run_a = _episode_dir(dataset / "run_a")
    run_b = _episode_dir(dataset / "run_b")

    result = compare_runs(run_a, run_b)

    assert result.is_drift is False
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


@pytest.mark.parametrize(
    "dataset",
    [
        Path("tests/golden/deterministic_run"),
        Path("tests/golden/veto_enforce"),
        Path("tests/golden/adr_008/allow_enforce"),
        Path("tests/golden/adr_008/veto_enforce"),
        Path("tests/golden/adr_008/fail_closed_error"),
        Path("tests/golden/adr_008/audit_veto"),
    ],
)
def test_golden_manifests_verify(dataset: Path) -> None:
    for run_dir in (_episode_dir(dataset / "run_a"), _episode_dir(dataset / "run_b")):
        report = verify_manifest(run_dir)
        assert report.status == "ok"
        assert list(report.issues) == []


def test_veto_golden_invariants() -> None:
    base = Path("tests/golden/veto_enforce")
    run = _episode_dir(base / "run_a")

    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["status"] == "vetoed"
    assert any(e["phase"] == "governance" and e["payload"].get("decision") == "veto" for e in events)
    assert any(
        e["phase"] == "direction"
        and e["payload"].get("status") == "blocked"
        and e["payload"].get("reason") == "governance_veto"
        for e in events
    )
    assert not any(e["phase"] == "act" for e in events)
