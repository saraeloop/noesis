"""Filesystem locking helpers for registry updates."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import fcntl

__all__ = ["file_lock"]


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """
    Acquire an exclusive POSIX file lock for the given path.

    This is a minimal, process-safe lock used for registry updates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
