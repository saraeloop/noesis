"""Process registry port contracts."""
from __future__ import annotations

from typing import Protocol, Sequence

from noesis.domain.process import Process

__all__ = ["ProcessRegistryPort", "ProcessRegistryFactoryPort"]


class ProcessRegistryPort(Protocol):
    """Port for persisting and querying process registry entries."""

    __api_version__: str = "process_registry/1.0"

    def get(self, process_id: str) -> Process | None:
        ...

    def get_by_name(self, process_name: str) -> Process | None:
        ...

    def list(self) -> Sequence[Process]:
        ...

    def upsert(self, process: Process) -> None:
        ...


class ProcessRegistryFactoryPort(Protocol):
    """Factory for process registry instances bound to a layout."""

    __api_version__: str = "process_registry_factory/1.0"

    def create(self, layout: object) -> ProcessRegistryPort:
        ...
