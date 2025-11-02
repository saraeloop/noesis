"""
Event emission ports expose the domain-friendly interface used by the application layer.
"""

from __future__ import annotations

from typing import Protocol

from noesis.domain.state.cognitive import CognitiveEvent

__all__ = ["EventWriterPort"]


class EventWriterPort(Protocol):
    """Port for persisting cognitive events."""

    def emit(self, event: CognitiveEvent, *, validate: bool = True) -> None:
        ...
