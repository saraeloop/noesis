"""
LangGraph adapter for Noēsis.
Bridges LangGraph node lifecycle events into Noēsis trace + intuition systems.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol
from os import PathLike

from ..trace.files import write_event
from ..intuition.base import Intuition, IntuitionEvent

__all__ = ["LangGraphAdapter", "Executor"]


class Executor(Protocol):
    """Backend execution contract expected by Noēsis."""
    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: PathLike[str] | str,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any: ...


@dataclass
class _State:
    """Minimal state snapshot carried across the run for advisory hooks."""
    history: list
    tools_seen: list


class LangGraphAdapter:
    """
    Wrap a LangGraph graph to emit Noēsis-compatible events and apply intuition.

    Notes:
      - Placeholder integration invokes `graph.run(task)`.
      - Future: attach to LangGraph node/tool callbacks for granular tracing.
    """

    def __init__(self, graph: Any) -> None:
        self.graph = graph
        self._state = _State(history=[], tools_seen=[])

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log(self, run_dir: PathLike[str] | str, episode_id: str, phase: str, payload: Dict[str, Any]) -> None:
        write_event(
            run_dir,
            {
                "timestamp": self._ts(),
                "episode_id": episode_id,
                "phase": phase,
                "payload": payload,
                "evidence_ids": payload.get("evidence_ids", []),
            },
        )

    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: PathLike[str] | str,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Pre-run advisory
        if intuition:
            evt: IntuitionEvent | None = intuition.advise(
                {
                    "task": task,
                    "seed": seed,
                    "history": self._state.history,
                    "tools_seen": self._state.tools_seen,
                    "tags": tags or {},
                }
            )
            if evt:
                self._log(
                    run_dir,
                    episode_id,
                    "intuition",
                    {
                        "kind": evt.kind,
                        "advice": evt.advice,
                        "confidence": evt.confidence,
                        "applied": evt.applied,
                        "rationale": evt.rationale,
                        "evidence_ids": evt.evidence_ids,
                    },
                )

        # Execution boundary
        self._log(run_dir, episode_id, "reason", {"note": "enter graph.run", "task": task})

        try:
            # Prefer `.run(task)`; fall back to callable(graph)(task).
            if hasattr(self.graph, "run"):
                result = self.graph.run(task)  # type: ignore[attr-defined]
            elif callable(self.graph):
                result = self.graph(task)      # type: ignore[call-arg]
            else:
                raise TypeError("graph object is neither runnable (.run) nor callable")

            self._log(run_dir, episode_id, "observe", {"result_excerpt": str(result)[:400]})
            self._log(run_dir, episode_id, "terminate", {"status": "ok"})
            return result

        except Exception as e:
            # Failure boundary
            self._log(run_dir, episode_id, "error", {"message": str(e)})
            self._log(run_dir, episode_id, "terminate", {"status": "error"})
            raise
