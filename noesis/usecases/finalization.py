"""Use-case writer for episode finalization markers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.artifacts.finalization import (
    FINAL_FILE_NAME,
    FinalOutcome,
    FinalVerificationStatus,
    FinalizationRecord,
)
from noesis.domain.artifacts.immutability import ArtifactWriteMode, ImmutabilityError
from noesis.domain.state import OUTCOME_STATUS_VETOED
from noesis.runtime.serialization import atomic_write_json
from noesis.usecases.immutability import ArtifactImmutabilityGuard
from noesis.usecases.verification_evaluator import OutcomeStatus

__all__ = [
    "FinalizationWriter",
    "map_outcome_to_final_outcome",
    "map_outcome_to_final_contract",
]

_OUTCOME_STATUS_TO_FINAL: dict[OutcomeStatus, tuple[FinalOutcome, FinalVerificationStatus]] = {
    "success": ("success", "verified"),
    "success_unverified": ("success", "unverified"),
    "goal_not_achieved": ("failed", "verified"),
    "error": ("error", "not_applicable"),
}


def map_outcome_to_final_outcome(outcome: OutcomeStatus) -> FinalOutcome:
    """Translate verification outcome into final outcome class (legacy helper)."""
    final_outcome, _ = map_outcome_to_final_contract(outcome=outcome)
    return final_outcome


def map_outcome_to_final_contract(
    *,
    outcome: OutcomeStatus,
    terminal_status: str | None = None,
) -> tuple[FinalOutcome, FinalVerificationStatus]:
    """
    Translate runtime status + verification outcome into final contract fields.

    Veto is an execution-class override when terminal status is explicitly vetoed.
    """
    if terminal_status == OUTCOME_STATUS_VETOED:
        return "vetoed", "not_applicable"
    mapped = _OUTCOME_STATUS_TO_FINAL.get(outcome)
    if mapped is None:  # pragma: no cover - defensive guard
        allowed = ", ".join(sorted(getattr(key, "value", str(key)) for key in _OUTCOME_STATUS_TO_FINAL.keys()))
        raise ValueError(f"unsupported outcome status for finalization: {outcome}; allowed: {allowed}")
    return mapped


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
