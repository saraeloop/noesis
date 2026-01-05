"""
Determinism replay gate for CI.

Checks:
- Minimal-mode golden pair under tests/golden/deterministic_run.
- Vetoed episode golden pair under tests/golden/veto_enforce.
- Real LLM replay golden pair under tests/golden/llm_real.

Fails with non-zero exit when drift is detected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from noesis.diagnostics import compare_runs


_MAX_DIR_ENTRIES = 8


def _format_entries(entries: Iterable[Path], *, debug: bool) -> str:
    names = sorted(entry.name for entry in entries)
    if debug or len(names) <= _MAX_DIR_ENTRIES:
        return ", ".join(names)
    shown = names[:_MAX_DIR_ENTRIES]
    remaining = len(names) - _MAX_DIR_ENTRIES
    return f"{', '.join(shown)}, ... +{remaining} more"


def _episode_dir(root: Path) -> Path:
    candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("ep_"))
    if not candidates:
        raise FileNotFoundError(f"fixture_hygiene: No ep_* directories found under {root}")
    if len(candidates) != 1:
        debug = bool(os.getenv("NOESIS_REPLAY_GATE_DEBUG"))
        entries = _format_entries((p for p in root.iterdir() if p.is_dir()), debug=debug)
        names = ", ".join(p.name for p in candidates)
        raise ValueError(
            f"fixture_hygiene: Expected exactly one ep_* directory under {root}. "
            f"Found ep_*: [{names}]. All dirs: [{entries}]"
        )
    return candidates[0]


def _assert_no_drift(label: str, a: Path, b: Path) -> None:
    result = compare_runs(a, b)
    if result.is_drift:
        mismatches = "; ".join(f"{m.artifact}: {m.detail}" for m in result.mismatches)
        raise RuntimeError(f"drift: {mismatches}")
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


def _check_adr_008_golden(name: str) -> None:
    base = Path("tests/golden/adr_008") / name
    run_a = _episode_dir(base / "run_a")
    run_b = _episode_dir(base / "run_b")
    _assert_no_drift(f"adr-008-{name}", run_a, run_b)


def main() -> int:
    checks = [
        ("minimal-golden", _check_minimal_golden, ()),
        ("veto-golden", _check_veto_golden, ()),
        ("llm-golden", _check_llm_golden, ()),
        ("adr-008-allow_enforce", _check_adr_008_golden, ("allow_enforce",)),
        ("adr-008-veto_enforce", _check_adr_008_golden, ("veto_enforce",)),
        ("adr-008-fail_closed_error", _check_adr_008_golden, ("fail_closed_error",)),
        ("adr-008-audit_veto", _check_adr_008_golden, ("audit_veto",)),
    ]
    try:
        for label, check, args in checks:
            try:
                check(*args)
            except Exception as exc:
                message = str(exc)
                if not message.startswith(("fixture_hygiene:", "drift:", "internal_error:")):
                    message = f"internal_error: {message}"
                raise RuntimeError(f"[{label}] {message}") from exc
    except Exception as exc:
        if os.getenv("NOESIS_REPLAY_GATE_DEBUG"):
            raise
        print(f"replay_gate failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
