"""Infrastructure adapters for workspace snapshots."""

__all__ = ["FileSystemSnapshotGateway", "FileSystemSnapshotMetadataStore", "UtcSnapshotClock"]

from .file_system_gateway import FileSystemSnapshotGateway
from .metadata_store import FileSystemSnapshotMetadataStore
from .clock import UtcSnapshotClock
