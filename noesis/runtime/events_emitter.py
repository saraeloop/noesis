"""
Infrastructure adapter for emitting cognitive events to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from noesis.domain.state.cognitive import CognitiveEvent
from noesis.trace.events import write_event

__all__ = ["CognitiveEventEmitter"]


class CognitiveEventEmitter:
    """Writes cognitive events to `events.jsonl` with optional validation."""

    __slots__ = ("_run_dir", "_agent_id")

    def __init__(self, *, run_dir: Path, agent_id: str = "system") -> None:
        self._run_dir = run_dir
        self._agent_id = agent_id

    def emit(self, event: CognitiveEvent, *, validate: bool = True, agent_id: Optional[str] = None) -> None:
        record = event.to_record()
        record["agent_id"] = agent_id or self._agent_id
        write_event(self._run_dir, record, validate=validate)

    def emit_many(self, events: Iterable[CognitiveEvent], *, validate: bool = True, agent_id: Optional[str] = None) -> None:
        for event in events:
            self.emit(event, validate=validate, agent_id=agent_id)
