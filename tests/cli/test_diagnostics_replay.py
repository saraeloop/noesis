from __future__ import annotations

from pathlib import Path

from noesis.cli import main as cli_main


def _episode_dir(root: Path) -> Path:
    candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("ep_"))
    assert candidates, f"no episode directories found under {root}"
    return candidates[0]


def test_cli_diagnostics_replay_no_drift(capsys) -> None:
    base = Path("tests/golden/deterministic_run")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")

    code = cli_main(["diagnostics", "replay", str(run_a), str(run_b)])

    captured = capsys.readouterr()
    assert code == 0
    assert "NO DRIFT" in captured.out
