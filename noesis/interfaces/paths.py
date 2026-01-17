"""Port contracts for resolving Noēsis filesystem layout."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from noesis.runtime.paths import NoesisPaths

__all__ = ["LayoutPort"]


class LayoutPort(Protocol):
    """Resolve and prepare the Noēsis on-disk layout."""

    __api_version__: str = "layout/1.0"

    def resolve(self, *, workspace: Path | None, runs_dir: Path) -> "NoesisPaths":
        ...

    def ensure(self, layout: "NoesisPaths") -> None:
        ...
