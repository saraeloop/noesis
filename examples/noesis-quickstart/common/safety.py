from __future__ import annotations

from pathlib import Path
from common.errors import ConfigError


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