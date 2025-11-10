"""Thread-safety helpers for NoesisSession."""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Callable, Iterator

__all__ = ["SessionLock"]


class SessionLock:
    """Re-entrant lock used to guard session-bound critical sections."""

    def __init__(self) -> None:
        self._lock = RLock()

    @contextmanager
    def scoped(self) -> Iterator[None]:
        """
        Acquire the lock for the duration of the context manager.

        Sessions default to one in-flight run at a time; callers that need
        concurrent runs should instantiate separate sessions.
        """
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()
