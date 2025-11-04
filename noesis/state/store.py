"""
Legacy escape hatch for the removed episode index shim.
"""

from __future__ import annotations

from ..deprecated import emit_legacy_warning, legacy_shims_enabled

if not legacy_shims_enabled():
    raise ImportError(
        "noesis.state.store has been removed; import EpisodeIndex from 'noesis.episode'.\n"
        "Set NOESIS_LEGACY_SHIMS=1 temporarily if you need the legacy shim."
    )

from warnings import warn

from noesis.infrastructure.episode.index_memory import EpisodeIndex
from noesis.interfaces.episode import EpisodeRecord

__all__ = ["EpisodeStore", "EpisodeRecord"]

emit_legacy_warning("noesis.state.store")
warn(
    "noesis.state.store is scheduled for removal; switch to noesis.episode.EpisodeIndex.",
    DeprecationWarning,
    stacklevel=2,
)

EpisodeStore = EpisodeIndex
