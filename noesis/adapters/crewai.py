"""CrewAI adapter built on top of the LangGraph bridge."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .langgraph import LangGraphAdapter
from .protocols import AdapterPath, DEFAULT_MIN_CONFIDENCE

__all__ = ["CrewAIAdapter"]


class _CrewGraph:
    """Wrap a CrewAI crew with a LangGraph-compatible interface."""

    def __init__(self, crew: Any) -> None:
        self._crew = crew

    def invoke(self, payload: Any) -> Any:
        if hasattr(self._crew, "kickoff"):
            return self._crew.kickoff(payload)
        if hasattr(self._crew, "run"):
            return self._crew.run(payload)
        if callable(self._crew):
            return self._crew(payload)
        # Minimal fallback: emit a structured plan so act/reflect events have context.
        return {
            "plan": [
                {"step": 1, "action": "analyse_task"},
                {"step": 2, "action": "draft_response"},
                {"step": 3, "action": "review_with_user"},
            ],
            "notes": payload,
        }


class CrewAIAdapter(LangGraphAdapter):
    """CrewAI integration that reuses the LangGraph instrumentation."""

    def __init__(
        self,
        crew: Any,
        *,
        input_mapper: Optional[Callable[[str], Any]] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        mapper = input_mapper or getattr(crew, "__noesis_input_mapper__", None) or (lambda task: {"task": task})
        super().__init__(
            _CrewGraph(crew),
            input_mapper=mapper,
            min_confidence=min_confidence,
        )
        self._crew = crew

    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: AdapterPath,
        intuition: Optional[Any] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return super().execute(
            task=task,
            episode_id=episode_id,
            run_dir=run_dir,
            intuition=intuition,
            seed=seed,
            tags=tags,
        )
