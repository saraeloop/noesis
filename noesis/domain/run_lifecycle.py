"""Domain contract for run interrupt/checkpoint/resume lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

RUN_LIFECYCLE_SCHEMA_VERSION: Final[str] = "run_lifecycle/1.0.0"
CHECKPOINT_SCHEMA_VERSION: Final[str] = "checkpoint/1.0.0"

RunLifecycleState = Literal[
    "running",
    "interrupted",
    "paused",
    "resuming",
    "success",
    "failed",
    "vetoed",
    "cancelled",
    "error",
]

TERMINAL_RUN_STATES: frozenset[RunLifecycleState] = frozenset(
    {"success", "failed", "vetoed", "cancelled", "error"}
)


class RunLifecycleError(RuntimeError):
    """Base error for run lifecycle contract violations."""


class RunSealedError(RunLifecycleError):
    """Raised when a lifecycle write targets a sealed run."""


class CheckpointNotFoundError(RunLifecycleError):
    """Raised when a requested checkpoint does not exist."""


class MissingCausalParentError(RunLifecycleError):
    """Raised when a lifecycle event cannot anchor to a causal parent."""


class CheckpointConsistencyError(RunLifecycleError):
    """Raised when checkpoint metadata no longer matches run history."""


class ResumeAdapterError(RunLifecycleError):
    """Base error for resume adapter contract violations."""


class ResumeAdapterRequiredError(ResumeAdapterError):
    """Raised when resume continuation requires an explicit adapter and none was supplied."""


class ResumeAdapterMismatchError(ResumeAdapterError):
    """Raised when resume continuation adapter differs from checkpoint adapter metadata."""


@dataclass(frozen=True, slots=True)
class RunCheckpoint:
    """Checkpoint pointer contract for append-only run artifacts."""

    schema_version: str
    run_id: str
    checkpoint_id: str
    created_at: str
    event_offset: int
    last_event_id: str
    state_hash: str
    artifact_manifest_hash: str
    adapter_label: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "event_offset": self.event_offset,
            "last_event_id": self.last_event_id,
            "state_hash": self.state_hash,
            "artifact_manifest_hash": self.artifact_manifest_hash,
        }
        if self.adapter_label:
            payload["adapter_label"] = self.adapter_label
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunCheckpoint":
        run_id = payload.get("run_id")
        checkpoint_id = payload.get("checkpoint_id")
        created_at = payload.get("created_at")
        last_event_id = payload.get("last_event_id")
        state_hash = payload.get("state_hash")
        artifact_manifest_hash = payload.get("artifact_manifest_hash")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("checkpoint.run_id must be a non-empty string")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise ValueError("checkpoint.checkpoint_id must be a non-empty string")
        if not isinstance(created_at, str) or not created_at:
            raise ValueError("checkpoint.created_at must be a non-empty string")
        if not isinstance(last_event_id, str) or not last_event_id:
            raise ValueError("checkpoint.last_event_id must be a non-empty string")
        if not isinstance(state_hash, str) or not state_hash:
            raise ValueError("checkpoint.state_hash must be a non-empty string")
        if not isinstance(artifact_manifest_hash, str) or not artifact_manifest_hash:
            raise ValueError("checkpoint.artifact_manifest_hash must be a non-empty string")
        adapter_label_raw = payload.get("adapter_label")
        adapter_label = (
            adapter_label_raw
            if isinstance(adapter_label_raw, str) and adapter_label_raw.strip()
            else None
        )
        event_offset = payload.get("event_offset")
        if not isinstance(event_offset, int) or event_offset < 1:
            raise ValueError("checkpoint.event_offset must be an integer >= 1")
        schema_version = payload.get("schema_version")
        if not isinstance(schema_version, str) or not schema_version:
            schema_version = CHECKPOINT_SCHEMA_VERSION
        return cls(
            schema_version=schema_version,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            created_at=created_at,
            event_offset=event_offset,
            last_event_id=last_event_id,
            state_hash=state_hash,
            artifact_manifest_hash=artifact_manifest_hash,
            adapter_label=adapter_label,
        )


__all__ = [
    "RUN_LIFECYCLE_SCHEMA_VERSION",
    "CHECKPOINT_SCHEMA_VERSION",
    "RunLifecycleState",
    "TERMINAL_RUN_STATES",
    "RunLifecycleError",
    "RunSealedError",
    "CheckpointNotFoundError",
    "MissingCausalParentError",
    "CheckpointConsistencyError",
    "ResumeAdapterError",
    "ResumeAdapterRequiredError",
    "ResumeAdapterMismatchError",
    "RunCheckpoint",
]
