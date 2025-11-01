from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence


def walk_upwards(start: Path) -> Iterable[Path]:
    """Yield directories from start up to filesystem root."""
    current = start
    while True:
        yield current
        if current.parent == current:
            break
        current = current.parent


def find_config_path(start: Path, candidates: Sequence[str]) -> Path | None:
    """Return the first matching config path when walking upwards from start."""
    for directory in walk_upwards(start):
        for candidate in candidates:
            path = directory / candidate
            if path.is_file():
                return path
    return None
