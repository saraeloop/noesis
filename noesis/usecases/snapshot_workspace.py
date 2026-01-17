"""Use case for capturing workspace snapshots via a gateway."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from noesis.domain.snapshot import DEFAULT_IGNORE, Snapshot, SnapshotGateway


@dataclass(slots=True)
class SnapshotWorkspace:
    """
    Capture workspace snapshots using a gateway.

    Integration note:
    EpisodeRunner/solve will invoke this use case before and after Act to
    persist pre/post snapshots into .noesis/episodes/<episode_id>/snapshots in a later PR.
    """

    gateway: SnapshotGateway

    def capture(self, workspace: Path, ignore: Sequence[str] = DEFAULT_IGNORE) -> Snapshot:
        """Capture a snapshot of the workspace using the configured gateway."""
        return self.gateway.capture(workspace=workspace, ignore=ignore)


__all__ = ["SnapshotWorkspace"]
