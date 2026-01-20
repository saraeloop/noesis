"""Runtime helpers for episode artifact immutability enforcement."""
from __future__ import annotations

from functools import lru_cache

from noesis.infrastructure.immutability import FinalizationSealStatus
from noesis.usecases.immutability import ArtifactImmutabilityGuard

APPEND_ONLY_ARTIFACTS = frozenset(
    {
        "events.jsonl",
        "prompts.jsonl",
        "learn.jsonl",
    }
)


@lru_cache(maxsize=1)
def default_artifact_guard() -> ArtifactImmutabilityGuard:
    """Return a shared immutability guard for episode artifact writers."""
    return ArtifactImmutabilityGuard(
        seal_status=FinalizationSealStatus(),
        append_only=APPEND_ONLY_ARTIFACTS,
    )


__all__ = ["APPEND_ONLY_ARTIFACTS", "default_artifact_guard"]
