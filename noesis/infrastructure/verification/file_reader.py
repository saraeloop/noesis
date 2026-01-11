"""Filesystem-backed reader for verification assertions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis.domain.verification import FileContentReader


@dataclass(slots=True)
class FileSystemFileReader(FileContentReader):
    """Read UTF-8 file contents relative to a workspace root."""

    root: Path

    def read_text(self, path: str) -> str:
        root = self.root.resolve()
        target = (root / Path(path)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path_outside_workspace: {path}") from exc
        return target.read_text(encoding="utf-8")


__all__ = ["FileSystemFileReader"]
