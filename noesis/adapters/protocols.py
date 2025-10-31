"""
Common adapter contracts for Noēsis integrations.

Each adapter is expected to expose an `execute` method that mirrors the core
runtime expectations so that `noesis.core.solve` can treat them uniformly.
This module centralizes the shared Protocol and small constants used across
adapter implementations.
"""

from __future__ import annotations

from os import PathLike
from typing import Any, Dict, Optional, Protocol

from ..intuition import Intuition

AdapterPath = PathLike[str] | str


class Adapter(Protocol):
    """Public adapter contract consumed by the core runtime."""

    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: AdapterPath,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        ...


class Executor(Protocol):
    """
    Internal adapter executor contract used for wrapping third-party graphs.

    LangGraph adapters leverage this to wrap compiled graphs that expose
    `invoke` or `run` entry points.
    """

    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: AdapterPath,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        ...


DEFAULT_MIN_CONFIDENCE = 0.5
STATE_HISTORY_LIMIT = 50


__all__ = [
    "Adapter",
    "Executor",
    "AdapterPath",
    "DEFAULT_MIN_CONFIDENCE",
    "STATE_HISTORY_LIMIT",
]
