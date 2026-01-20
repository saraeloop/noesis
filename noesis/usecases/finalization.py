"""Use-case writer for episode finalization markers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.artifacts.finalization import FINAL_FILE_NAME, FinalizationRecord
from noesis.domain.artifacts.immutability import ArtifactWriteMode, ImmutabilityError
from noesis.runtime.serialization import atomic_write_json
from noesis.usecases.immutability import ArtifactImmutabilityGuard

__all__ = ["FinalizationWriter"]


@dataclass(frozen=True, slots=True)
class FinalizationWriter:
    """Write final.json once at the end of an episode."""

    immutability_guard: ArtifactImmutabilityGuard

    def write(self, *, episode_dir: Path, record: FinalizationRecord) -> Path:
        path = episode_dir / FINAL_FILE_NAME
        if path.exists():
            raise ImmutabilityError(
                f"finalization marker already exists: {path}",
                episode_dir=episode_dir,
                artifact=FINAL_FILE_NAME,
                mode=ArtifactWriteMode.CREATE,
            )
        self.immutability_guard.ensure_write_allowed(
            episode_dir=episode_dir,
            artifact=FINAL_FILE_NAME,
            mode=ArtifactWriteMode.CREATE,
        )
        atomic_write_json(path, record.to_dict())
        return path
