"""Default session provider used by module-level helpers."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from threading import RLock
from typing import Iterator

from .models import SessionBuilder
from .session import NoesisSession

__all__ = ["DefaultSessionProvider"]


class DefaultSessionProvider:
    """Builds and memoizes the process-level default session."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._default_session: NoesisSession | None = None
        self._scoped_session: ContextVar[NoesisSession | None] = ContextVar(
            "noesis_session_override",
            default=None,
        )

    def current(self) -> NoesisSession:
        """Return the active session (scoped override > process default)."""
        scoped = self._scoped_session.get()
        if scoped is not None:
            return scoped
        with self._lock:
            if self._default_session is None:
                self._default_session = SessionBuilder.from_env().build()
            return self._default_session

    @contextmanager
    def use(self, session: NoesisSession) -> Iterator[None]:
        """
        Temporarily set a scoped session (e.g., within a CLI invocation or test).
        """
        token: Token[NoesisSession | None] = self._scoped_session.set(session)
        try:
            yield
        finally:
            self._scoped_session.reset(token)
