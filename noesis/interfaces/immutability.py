"""Ports for artifact immutability checks."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

__all__ = ["SealStatusPort"]


class SealStatusPort(Protocol):
    """Port for checking whether an episode run has been sealed."""

    def is_sealed(self, run_dir: Path) -> bool:
        ...

    def seal_marker(self, run_dir: Path) -> Path:
        ...
