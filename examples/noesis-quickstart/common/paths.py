from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.errors import ConfigError


@dataclass(frozen=True)
class QuickstartPaths:
    root: Path
    runs: Path
    sandbox: Path


def get_paths() -> QuickstartPaths:
    """
    Canonical layout for this repo.
    - runs/: where episodes + reports go
    - .sandbox/: safe filesystem demo area
    """
    root = Path(__file__).resolve().parent.parent
    runs = root / "runs"
    sandbox = root / ".sandbox"

    runs.mkdir(parents=True, exist_ok=True)
    sandbox.mkdir(parents=True, exist_ok=True)

    return QuickstartPaths(root=root, runs=runs, sandbox=sandbox)


def tutorial_runs_dir(tutorial_slug: str) -> Path:
    p = get_paths().runs / tutorial_slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def tutorial_sandbox_dir(tutorial_slug: str) -> Path:
    p = get_paths().sandbox / tutorial_slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_under_root(root: Path, target: Path) -> None:
    """
    Enforce sandbox-only operations: target must be within root.
    """
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except Exception:
        raise ConfigError(f"Unsafe path: {target} is not under sandbox root {root}")
