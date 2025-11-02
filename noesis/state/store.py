"""
Deprecated shim for the episode index.

This module will be removed in v0.8.0. Import from
`noesis.infrastructure.episode.index_memory` instead.
"""

from __future__ import annotations

from warnings import warn

from noesis.infrastructure.episode.index_memory import EpisodeIndex
from noesis.interfaces.episode import EpisodeRecord

__all__ = ["EpisodeStore", "EpisodeRecord"]

warn(
    "noesis.state.store is deprecated and will be removed in v0.8.0; "
    "use noesis.infrastructure.episode.index_memory.EpisodeIndex instead.",
    DeprecationWarning,
    stacklevel=2,
)

EpisodeStore = EpisodeIndex
