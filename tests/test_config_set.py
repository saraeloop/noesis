from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import noesis as ns


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def test_set_records_runs_dir_without_creating(tmp_path):
    runs_dir = tmp_path / "custom-runs"
    with _preserve_config():
        ns.set(runs_dir=runs_dir)
        assert not runs_dir.exists()
        assert Path(ns.get()["runs_dir"]).resolve() == runs_dir.resolve()
