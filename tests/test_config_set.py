from __future__ import annotations

from pathlib import Path

import noesis as ns


def test_set_creates_runs_dir(tmp_path):
    runs_dir = tmp_path / "custom-runs"
    ns.set(runs_dir=runs_dir)
    assert runs_dir.exists()
    assert Path(ns.get()["runs_dir"]).resolve() == runs_dir.resolve()
