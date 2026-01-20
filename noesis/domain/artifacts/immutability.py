"""Domain contracts for episode artifact immutability."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

__all__ = [
    "ArtifactWriteMode",
    "ArtifactWriteRequest",
    "ImmutabilityDecision",
    "ImmutabilityError",
]


class ArtifactWriteMode(str, Enum):
    """Normalized write modes for episode artifacts."""

    APPEND = "append"
    CREATE = "create"
    OVERWRITE = "overwrite"
    SEAL = "seal"


@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    """Describe an attempted artifact write."""

    episode_dir: Path
    artifact: str
    mode: ArtifactWriteMode

    @property
    def run_dir(self) -> Path:
        """Back-compat alias for episode_dir."""
        return self.episode_dir


@dataclass(frozen=True, slots=True)
class ImmutabilityDecision:
    """Outcome of an immutability guard check."""

    allowed: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.allowed and not self.reason:
            raise ValueError("ImmutabilityDecision.reason required when disallowed")


class ImmutabilityError(RuntimeError):
    """Raised when a write violates the immutability policy."""

    def __init__(
        self,
        message: str,
        *,
        episode_dir: Path,
        artifact: str,
        mode: ArtifactWriteMode,
    ) -> None:
        super().__init__(message)
        self.episode_dir = episode_dir
        self.artifact = artifact
        self.mode = mode
