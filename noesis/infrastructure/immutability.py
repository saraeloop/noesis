"""Filesystem-backed immutability checks for episode artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.interfaces.immutability import SealStatusPort
from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME

__all__ = ["ManifestSealStatus"]


@dataclass(frozen=True, slots=True)
class ManifestSealStatus(SealStatusPort):
    """Treat presence of manifest.json as the episode seal."""

    def is_sealed(self, run_dir: Path) -> bool:
        return (run_dir / MANIFEST_FILE_NAME).exists()

    def seal_marker(self, run_dir: Path) -> Path:
        return run_dir / MANIFEST_FILE_NAME
