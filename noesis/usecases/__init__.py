"""
Use-case layer (application services) for Noēsis.

This package defines orchestrators (e.g., EpisodeRunner) and ports that
separate domain logic from infrastructure concerns.

Compatibility note: This module uses a small lazy-import shim to preserve
historical import paths without importing heavy modules at package import time.
Internal code should prefer explicit imports from concrete modules.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "EpisodeRunner",
    "EpisodeDependencies",
    "EpisodeInstrumentation",
    "EpisodeRequest",
    "EpisodeResult",
    "EpisodeOutcome",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - import shim
    if name in __all__:
        from . import episode_runner as _episode_runner

        return getattr(_episode_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:  # pragma: no cover - tooling ergonomics
    return sorted(set(list(globals().keys()) + __all__))
