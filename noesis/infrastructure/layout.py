"""Filesystem-backed layout resolver for Noēsis artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.interfaces.paths import LayoutPort
from noesis.runtime.paths import NoesisPaths, resolve_noesis_paths

__all__ = ["FileSystemLayoutResolver"]


@dataclass(slots=True)
class FileSystemLayoutResolver(LayoutPort):
    """Resolve layout paths and ensure directories exist."""

    __api_version__ = "layout/1.0"

    def resolve(self, *, workspace: Path | None, runs_dir: Path) -> NoesisPaths:
        return resolve_noesis_paths(workspace=workspace, runs_dir=runs_dir)

    def ensure(self, layout: NoesisPaths) -> None:
        layout.root.mkdir(parents=True, exist_ok=True)
        layout.episodes_dir.mkdir(parents=True, exist_ok=True)
        layout.processes_dir.mkdir(parents=True, exist_ok=True)
