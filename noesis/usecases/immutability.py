"""Use-case guard for enforcing episode artifact immutability."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from noesis.domain.artifacts.immutability import (
    ArtifactWriteMode,
    ArtifactWriteRequest,
    ImmutabilityDecision,
    ImmutabilityError,
)
from noesis.interfaces.immutability import SealStatusPort

__all__ = ["ArtifactImmutabilityGuard"]


@dataclass(frozen=True, slots=True)
class ArtifactImmutabilityGuard:
    """Centralized policy guard for episode artifact writes."""

    seal_status: SealStatusPort
    append_only: frozenset[str] = frozenset()

    def check(self, request: ArtifactWriteRequest) -> ImmutabilityDecision:
        run_dir = request.episode_dir
        artifact = request.artifact
        mode = request.mode
        if self.seal_status.is_sealed(run_dir):
            marker = self.seal_status.seal_marker(run_dir)
            reason = f"episode sealed by {marker}"
            return ImmutabilityDecision(allowed=False, reason=reason)
        if artifact in self.append_only and mode is ArtifactWriteMode.OVERWRITE:
            return ImmutabilityDecision(
                allowed=False,
                reason=f"append-only artifact requires append: {artifact}",
            )
        if artifact not in self.append_only and mode is ArtifactWriteMode.APPEND:
            return ImmutabilityDecision(
                allowed=False,
                reason=f"append-only write requested for non-append artifact: {artifact}",
            )
        return ImmutabilityDecision(allowed=True, reason=None)

    def ensure_write_allowed(
        self,
        *,
        episode_dir: Path,
        artifact: str,
        mode: ArtifactWriteMode,
    ) -> None:
        normalized = _normalize_artifact_path(artifact, episode_dir=episode_dir)
        request = ArtifactWriteRequest(episode_dir=episode_dir, artifact=normalized, mode=mode)
        decision = self.check(request)
        if decision.allowed:
            return
        reason = decision.reason
        message = f"{reason}; refusing to {mode.value} {normalized}"
        raise ImmutabilityError(
            message,
            episode_dir=episode_dir,
            artifact=normalized,
            mode=mode,
        )


def _normalize_artifact_path(raw: str, *, episode_dir: Path) -> str:
    """
    Normalize and validate an artifact path.

    - Reject absolute paths.
    - Reject any '..' segments.
    - Normalize to POSIX separators.
    """
    if not raw:
        raise ImmutabilityError(
            "artifact path is required",
            episode_dir=episode_dir,
            artifact=raw,
            mode=ArtifactWriteMode.OVERWRITE,
        )
    normalized = str(raw).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or normalized.startswith("/"):
        raise ImmutabilityError(
            f"artifact path must be relative: {raw}",
            episode_dir=episode_dir,
            artifact=raw,
            mode=ArtifactWriteMode.OVERWRITE,
        )
    if path.parts and ":" in path.parts[0]:
        raise ImmutabilityError(
            f"artifact path must be relative: {raw}",
            episode_dir=episode_dir,
            artifact=raw,
            mode=ArtifactWriteMode.OVERWRITE,
        )
    if ".." in path.parts:
        raise ImmutabilityError(
            f"artifact path must not escape episode dir: {raw}",
            episode_dir=episode_dir,
            artifact=raw,
            mode=ArtifactWriteMode.OVERWRITE,
        )
    return path.as_posix().lstrip("./")
