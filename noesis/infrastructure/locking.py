"""Filesystem locking helpers for registry updates."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import os

try:  # pragma: no cover - platform-specific import
    import fcntl  # type: ignore
except Exception:  # noqa: BLE001
    fcntl = None  # type: ignore

try:  # pragma: no cover - platform-specific import
    import msvcrt  # type: ignore
except Exception:  # noqa: BLE001
    msvcrt = None  # type: ignore

__all__ = ["file_lock"]


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """
    Acquire an exclusive POSIX file lock for the given path.

    This is a minimal, process-safe lock used for registry updates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
            return
        if msvcrt is not None and os.name == "nt":
            handle.seek(0)
            handle.write("0")
            handle.flush()
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        yield