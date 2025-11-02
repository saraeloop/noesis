"""
Episode index port definitions.

Defines the contracts used by application and runtime layers to record and
query lightweight episode metadata without binding to a specific storage
backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Protocol, Sequence, Tuple

__all__ = ["EpisodeRecord", "EpisodeIndexPort"]


@dataclass(slots=True)
class EpisodeRecord:
    """Immutable snapshot of an episode entry stored in the manifest."""

    episode_id: str
    created_at: str
    summary_path: str
    state_path: str
    status: str
    task: str
    using: Optional[str]
    expires_at: Optional[str]
    provenance: Dict[str, str]


class EpisodeIndexPort(Protocol):
    """Port abstraction for persisting and querying episode summaries."""

    def append(
        self,
        *,
        episode_id: str,
        summary_path: Path | str,
        state_path: Path | str,
        status: str,
        task: str,
        using: Optional[str],
        provenance: Optional[Dict[str, str]] = None,
        embedding: Optional[Iterable[float]] = None,
    ) -> EpisodeRecord:
        ...

    def iter(self, *, include_expired: bool = False) -> Iterator[EpisodeRecord]:
        ...

    def vacuum(self) -> int:
        ...

    def search(self, embedding: Iterable[float], k: int = 5) -> Sequence[Tuple[str, float]]:
        ...
