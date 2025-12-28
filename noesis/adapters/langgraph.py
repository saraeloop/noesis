"""
LangGraph adapter for Noēsis (thin wrapper).

This adapter does not emit events or enforce governance; it simply adapts
graph invocation so EpisodeRunner owns the cognitive loop.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .protocols import Executor

__all__ = ["LangGraphAdapter", "Executor"]


def _resolve_input_mapper(graph: Any, mapper: Optional[Callable[[str], Any]]) -> Callable[[str], Any]:
    if mapper is not None:
        return mapper
    discovered = getattr(graph, "__noesis_input_mapper__", None)
    return discovered if callable(discovered) else (lambda t: t)


def _invoke(graph: Any, payload: Any) -> Any:
    if hasattr(graph, "invoke"):
        return graph.invoke(payload)
    if hasattr(graph, "run"):
        return graph.run(payload)
    if callable(graph):
        return graph(payload)
    raise TypeError("object is neither runnable nor callable")


def _resolve_result(result: Any) -> Any:
    if inspect.isawaitable(result):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        raise RuntimeError("cannot await LangGraph result while an event loop is running")
    return result


@dataclass(slots=True)
class LangGraphAdapter:
    """Adapter that normalizes LangGraph invocation to a callable interface."""

    graph: Any
    input_mapper: Optional[Callable[[str], Any]] = None

    def __post_init__(self) -> None:
        self.input_mapper = _resolve_input_mapper(self.graph, self.input_mapper)

    def invoke(self, task: str) -> Any:
        payload = self.input_mapper(task) if self.input_mapper else task
        return _resolve_result(_invoke(self.graph, payload))

    def run(self, task: str) -> Any:
        return self.invoke(task)

    def __call__(self, task: str) -> Any:
        return self.invoke(task)

    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: Any,
        intuition: Any | None = None,
        seed: int = 0,
        tags: dict[str, Any] | None = None,
    ) -> Any:
        """Legacy adapter entrypoint retained for compatibility."""
        _ = (episode_id, run_dir, intuition, seed, tags)
        return self.invoke(task)
