"""Domain models and helpers for stable process identity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal

ProcessKind = Literal["oneshot", "loop", "workflow"]
ProcessStatus = Literal["running", "idle", "stale", "error"]

PROCESS_SCHEMA_VERSION = "process/1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@dataclass(slots=True, frozen=True)
class Process:
    """
    Stable process identity with lifecycle metadata.

    process_id: Opaque, stable identifier derived from workspace + optional name.
    process_name: Human label shown in operator views (explicit or auto-derived).
    kind: Execution style that frames expectations (oneshot/loop/workflow).
    status: Minimal liveness/health indicator for operators.
    created_at: First time this process identity was registered.
    last_seen_at: Last time the process emitted or updated a run.
    active_run_id: Current run/episode id if one is active.
    last_run_outcome: Outcome string from the most recent completed run.
    run_index: Monotonic per-process run counter (used for labels like #3).
    """

    process_id: str
    process_name: str
    kind: ProcessKind = "oneshot"
    status: ProcessStatus = "idle"
    created_at: datetime = field(default_factory=_utc_now)
    last_seen_at: datetime = field(default_factory=_utc_now)
    active_run_id: str | None = None
    last_run_outcome: str | None = None
    run_index: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "process_id": self.process_id,
            "process_name": self.process_name,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "active_run_id": self.active_run_id,
            "last_run_outcome": self.last_run_outcome,
            "run_index": self.run_index,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Process":
        created_at = payload.get("created_at")
        last_seen_at = payload.get("last_seen_at")
        if not isinstance(created_at, str) or not isinstance(last_seen_at, str):
            raise ValueError("process payload missing timestamps")
        process_id = payload.get("process_id")
        process_name = payload.get("process_name")
        if not isinstance(process_id, str) or not process_id:
            raise ValueError("process payload missing process_id")
        if not isinstance(process_name, str) or not process_name:
            raise ValueError("process payload missing process_name")
        kind = payload.get("kind")
        status = payload.get("status")
        return cls(
            process_id=process_id,
            process_name=process_name,
            kind=kind if isinstance(kind, str) else "oneshot",  # type: ignore[assignment]
            status=status if isinstance(status, str) else "idle",  # type: ignore[assignment]
            created_at=_parse_iso(created_at),
            last_seen_at=_parse_iso(last_seen_at),
            active_run_id=payload.get("active_run_id") if payload.get("active_run_id") else None,
            last_run_outcome=payload.get("last_run_outcome") if payload.get("last_run_outcome") else None,
            run_index=int(payload.get("run_index", 0)),
        )


@dataclass(slots=True, frozen=True)
class ProcessIdentity:
    """Derived identity tuple for process registration."""

    process_id: str
    process_name: str


def derive_process_identity(*, workspace_identity: str, process_name: str | None = None) -> ProcessIdentity:
    """
    Derive a stable process id and display name from workspace + optional name.

    workspace_identity should already be normalized and deterministic (e.g. a
    resolved workspace path from the outer layer).
    """
    normalized_workspace = workspace_identity.strip()
    if not normalized_workspace:
        raise ValueError("workspace_identity must be a non-empty string")
    normalized_name = process_name.strip() if process_name else ""
    seed = f"{normalized_workspace}|{normalized_name}" if normalized_name else normalized_workspace
    digest = sha256(seed.encode("utf-8")).hexdigest()
    process_id = digest[:12]
    if normalized_name:
        display_name = normalized_name
    else:
        base = Path(normalized_workspace).name or "workspace"
        display_name = f"{base}-{process_id[:6]}"
    return ProcessIdentity(process_id=process_id, process_name=display_name)


__all__ = [
    "PROCESS_SCHEMA_VERSION",
    "Process",
    "ProcessIdentity",
    "ProcessKind",
    "ProcessStatus",
    "derive_process_identity",
]
