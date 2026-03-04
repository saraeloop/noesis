"""Domain contract for episode finalization markers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FINAL_FILE_NAME = "final.json"
FINAL_SCHEMA_VERSION = "final/2.0.0"

FinalOutcome = Literal[
    "success",
    "failed",
    "vetoed",
    "cancelled",
    "interrupted",
    "error",
]

FinalVerificationStatus = Literal[
    "verified",
    "unverified",
    "not_applicable",
]

__all__ = [
    "FINAL_FILE_NAME",
    "FINAL_SCHEMA_VERSION",
    "FinalizationRecord",
    "FinalOutcome",
    "FinalVerificationStatus",
]


@dataclass(frozen=True, slots=True)
class FinalizationRecord:
    """Canonical payload for final.json."""

    episode_id: str
    process_id: str
    run_index: int
    finalized_at: str
    outcome: FinalOutcome
    verification_status: FinalVerificationStatus
    schema_version: str = FINAL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "process_id": self.process_id,
            "run_index": self.run_index,
            "finalized_at": self.finalized_at,
            "outcome": self.outcome,
            "verification_status": self.verification_status,
        }
