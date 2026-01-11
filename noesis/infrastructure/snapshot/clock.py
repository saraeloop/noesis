"""Clock implementation for snapshot capture timestamps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from noesis.usecases.snapshot_artifacts import SnapshotClock


@dataclass(slots=True)
class UtcSnapshotClock:
    """UTC clock returning ISO-8601 timestamps with timezone."""

    def now_utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = ["UtcSnapshotClock"]
