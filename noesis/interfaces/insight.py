"""Insight scoring port definitions."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

__all__ = ["InsightPort"]


class InsightPort(Protocol):
    """Port contract for computing task-level insight metrics (1.0-rc1)."""

    __api_version__: str = "insight/1.0-rc1"

    def supports(self, capability: str) -> bool:
        """Return True if the adapter exposes a named capability."""

    def compute_task_score(
        self,
        *,
        goal: str,
        summary: Mapping[str, Any],
        metrics: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Compute and return task scoring artefacts."""
