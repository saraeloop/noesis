"""Memory port definitions for the cognitive framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

__all__ = ["Fact", "MemoryQuery", "MemoryPort"]


@dataclass(frozen=True, slots=True)
class Fact:
    """Lightweight fact record stored in persistent memory."""

    id: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    """Query descriptor for retrieving relevant facts."""

    text: str
    filters: Mapping[str, Any] = field(default_factory=dict)


class MemoryPort(Protocol):
    """Port contract for memory adapters (1.0-rc1)."""

    __api_version__: str = "memory/1.0-rc1"

    def supports(self, capability: str) -> bool:
        """Return True if the adapter exposes a named capability."""

    def write_fact(self, fact: Fact) -> None:
        """Persist a fact into the memory store."""

    def query(self, query: MemoryQuery, *, k: int = 5) -> Sequence[Fact]:
        """Retrieve the top-k facts matching a query."""

    def link_episode(self, episode_id: str, fact_ids: Sequence[str]) -> None:
        """Associate an episode with a set of fact identifiers."""
