"""
Test-only LLM transcript helpers for offline replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from noesis.trace.events import canonical_dumps

TRANSCRIPT_VERSION = "1.0"


def write_transcript(path: Path, entries: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(canonical_dumps(entry) + "\n")


def read_transcript(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


@dataclass(slots=True)
class ReplayLLMProvider:
    """Callable provider that replays recorded payloads in order."""

    transcript_path: Path
    _entries: list[dict[str, Any]] = field(init=False, repr=False)
    _index: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        self._entries = read_transcript(self.transcript_path)

    def __call__(self, _state: Mapping[str, Any]) -> Mapping[str, Any]:
        if self._index >= len(self._entries):
            raise RuntimeError("Replay transcript exhausted; no more entries")
        entry = self._entries[self._index]
        self._index += 1
        response = entry.get("response", {})
        payload = response.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("Replay transcript entry is missing response payload")
        return dict(payload)


__all__ = [
    "TRANSCRIPT_VERSION",
    "write_transcript",
    "read_transcript",
    "ReplayLLMProvider",
]
