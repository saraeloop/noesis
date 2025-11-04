from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("libcst")

from noesis.tools.migrate import run_migration


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_run_migration_updates_symbols(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "example.py",
        """
from noesis.summary import load
from noesis.events import start_event
from noesis.state.store import EpisodeStore

result = load("episode")
start_event(None, "episode", {})
store: EpisodeStore | None = None
""",
    )

    report = run_migration([path], apply=True)

    updated = path.read_text()
    assert "from noesis.summary import read" in updated
    assert "from noesis.events import start" in updated
    assert "from noesis.episode import EpisodeIndex" in updated
    assert "result = read(" in updated
    assert "start(" in updated
    assert report.renamed > 0
    assert report.replaced > 0
    assert not report.todo, "expected no TODO entries for handled replacements"


def test_run_migration_collects_todo(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "alias.py",
        """
from noesis import summary

def helper():
    return summary.load("ep")
""",
    )

    report = run_migration([path], apply=False)
    assert not report.todo


def test_run_migration_idempotent(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "idempotent.py",
        """
from noesis.summary import load

def fetch(ep):
    return load(ep)
""",
    )

    first = run_migration([path], apply=True)
    assert first.changed_files == 1

    second = run_migration([path], apply=True)
    assert second.changed_files == 0
    assert second.renamed == 0
    assert second.replaced == 0


def test_star_import_reported(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "star.py",
        """
from noesis.summary import *

def helper():
    return load("ep")
""",
    )

    report = run_migration([path], apply=False)
    todo = report.todo.get(str(path), set())
    assert "from noesis.summary import *" in todo


def test_alias_preserved(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "alias_preserved.py",
        """
from noesis.summary import load as sl

def helper():
    return sl("ep")
""",
    )

    report = run_migration([path], apply=True)
    updated = path.read_text()
    assert "from noesis.summary import read as sl" in updated
    assert "sl(\"ep\")" in updated
    assert report.renamed > 0
