"""
Infrastructure layer exports for Noēsis.

Compatibility note: This module uses a small lazy-import shim to preserve
historical import paths while avoiding import cycles at package import time.
Internal code should prefer explicit imports from concrete modules.
"""

from __future__ import annotations

from typing import Any

__all__ = ["config", "RuntimeStateRepository"]


def __getattr__(name: str) -> Any:  # pragma: no cover - import shim
    if name == "config":
        from . import config as _config

        return _config
    if name == "RuntimeStateRepository":
        from .state_repository import RuntimeStateRepository

        return RuntimeStateRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:  # pragma: no cover - tooling ergonomics
    return sorted(set(list(globals().keys()) + __all__))
