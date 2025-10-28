"""
LangGraph adapter for Noēsis.

Bridges LangGraph node lifecycle events into Noēsis trace + intuition systems.

Responsibilities:
  • Translate LangGraph callbacks into Noēsis event schema.
  • Maintain lightweight state snapshots for intuition probes.
  • Inject directional hints (pre/post node execution).
  • Handle graceful termination and summary finalization.

This adapter enables running standard LangGraph graphs under Noēsis
with full introspection, traceability, and A/B testing for intuition policies.

References:
  - Integrates with LangGraph (MIT License)
    © 2024 LangChain Inc.  https://github.com/langchain-ai/langgraph
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol

from ..trace import write_event
from ..intuition import Intuition, IntuitionEvent


# Executor contract
class Executor(Protocol):
    """Minimal execution contract Noēsis expects from any backend."""
    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir,  # Path-like; duck-typed to avoid import cycles
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any: ...


# Registry 
_GRAPH_REGISTRY: Dict[str, Callable[[], Any]] = {}


def register_graph(name: str, factory: Callable[[], Any]) -> None:
    """Register a LangGraph factory under a human-friendly key."""
    key = name.strip().lower()
    if not key:
        raise ValueError("graph name must be non-empty")
    _GRAPH_REGISTRY[key] = factory


def create_graph(name: str) -> Any:
    """Instantiate a previously-registered graph by key."""
    key = name.strip().lower()
    try:
        return _GRAPH_REGISTRY[key]()
    except KeyError:
        available = ", ".join(sorted(_GRAPH_REGISTRY.keys()))
        raise ValueError(f"unknown graph '{name}'. registered: [{available}]") from None



# LangGraphAdapter
@dataclass
class _State:
    history: list
    tools_seen: list


class LangGraphAdapter:
    """
    Wrap a LangGraph graph to emit Noēsis-compatible events and apply intuition.

    Usage:
        graph = create_graph("react")         # via registry
        adapter = LangGraphAdapter(graph)
        adapter.execute(task=..., episode_id=..., run_dir=..., intuition=policy)

    Notes:
      - Today we call `graph.run(task)` as a placeholder. In a later pass,
        attach LangGraph node/tool callbacks to capture granular events.
    """

    def __init__(self, graph: Any) -> None:
        self.graph = graph
        self._state = _State(history=[], tools_seen=[])

    # helpers 
    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log(self, run_dir, episode_id: str, phase: str, payload: Dict[str, Any]) -> None:
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

    # execution 
    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Pre-run intuition (directional hint)
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

        # TODO: hook LangGraph callbacks to emit per-node/tool events.
        self._log(run_dir, episode_id, "reason", {"note": "enter graph.run", "task": task})

        try:
            # Placeholder API; adjust to your concrete LangGraph interface.
            result = self.graph.run(task)
            self._log(run_dir, episode_id, "observe", {"result_excerpt": str(result)[:400]})
            self._log(run_dir, episode_id, "terminate", {"status": "ok"})
            return result

        except Exception as e:
            # TODO: map exception types to structured error payloads.
            self._log(run_dir, episode_id, "error", {"message": str(e)})
            self._log(run_dir, episode_id, "terminate", {"status": "error"})
            raise