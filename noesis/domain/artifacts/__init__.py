"""Domain artifacts namespace."""

from .finalization import (
    FINAL_FILE_NAME,
    FINAL_SCHEMA_VERSION,
    FinalizationRecord,
    FinalOutcome,
    FinalVerificationStatus,
)
from .immutability import (
    ArtifactWriteMode,
    ArtifactWriteRequest,
    ImmutabilityDecision,
    ImmutabilityError,
)

__all__ = [
    "ArtifactWriteMode",
    "ArtifactWriteRequest",
    "ImmutabilityDecision",
    "ImmutabilityError",
    "FINAL_FILE_NAME",
    "FINAL_SCHEMA_VERSION",
    "FinalizationRecord",
    "FinalOutcome",
    "FinalVerificationStatus",
]
