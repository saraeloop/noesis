"""Filesystem-backed immutability checks for episode artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.artifacts.finalization import FINAL_FILE_NAME
from noesis.interfaces.immutability import SealStatusPort

__all__ = ["FinalizationSealStatus"]


@dataclass(frozen=True, slots=True)
class FinalizationSealStatus(SealStatusPort):
    """Treat presence of final.json as the canonical seal."""

    def is_sealed(self, episode_dir: Path) -> bool:
        return (episode_dir / FINAL_FILE_NAME).exists()

    def seal_marker(self, episode_dir: Path) -> Path:
        return episode_dir / FINAL_FILE_NAME
