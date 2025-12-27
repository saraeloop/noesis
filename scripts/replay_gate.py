"""
Determinism replay gate for CI.

Checks:
- Minimal-mode golden pair under tests/golden/deterministic_run.
- Vetoed episode golden pair under tests/golden/veto_enforce.
- Real LLM replay golden pair under tests/golden/llm_real.

Fails with non-zero exit when drift is detected.
"""

from __future__ import annotations

import sys
from pathlib import Path

from noesis.diagnostics import compare_runs


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


def _check_minimal_golden() -> None:
    base = Path("tests/golden/deterministic_run")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")
    _assert_no_drift("minimal-golden", run_a, run_b)


def _check_veto_golden() -> None:
    base = Path("tests/golden/veto_enforce")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")
    _assert_no_drift("veto-golden", run_a, run_b)


def _check_llm_golden() -> None:
    base = Path("tests/golden/llm_real")
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")
    _assert_no_drift("llm-golden", run_a, run_b)


def main() -> int:
    try:
        _check_minimal_golden()
        _check_veto_golden()
        _check_llm_golden()
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
