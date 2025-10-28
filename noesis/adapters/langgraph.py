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
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timezone

from ..trace import write_event
from ..intuition import Intuition, IntuitionEvent

class LangGraphAdapter:
    """
    Wraps a LangGraph instance to emit Noēsis-compatible events and apply intuition.

    Example
    -------
    >>> adapter = LangGraphAdapter(graph=my_graph, episode_id="ep_20251027_s1")
    >>> adapter.run(task="Analyze model logs")
    """

    def __init__(self, graph: Any, episode_id: str, intuition: Optional[Intuition] = None):
        self.graph = graph
        self.episode_id = episode_id
        self.intuition = intuition
        self.state: Dict[str, Any] = {"history": [], "tools_seen": []}

    def _log_event(self, phase: str, payload: Dict[str, Any]) -> None:
        """Internal helper to standardize event writing."""
        ts = datetime.now(timezone.utc).isoformat()
        write_event(self._run_dir, {
            "timestamp": ts,
            "episode_id": self.episode_id,
            "phase": phase,
            "payload": payload,
            "evidence_ids": payload.get("evidence_ids", []),
        })

    def run(self, task: str, **kwargs: Any) -> None:
        """
        Executes the wrapped LangGraph with intuition hooks.
        Logs reasoning, actions, and outcomes via Noēsis.
        """
        self._log_event("start", {"task": task})

        # Pre-run intuition
        if self.intuition:
            evt: IntuitionEvent | None = self.intuition.advise({
                "task": task,
                "history": self.state["history"],
                "tools_seen": self.state["tools_seen"],
            })
            if evt:
                self._log_event("intuition", {
                    "kind": evt.kind,
                    "advice": evt.advice,
                    "confidence": evt.confidence,
                    "applied": evt.applied,
                    "rationale": evt.rationale,
                })

        # TODO: Connect LangGraph event hooks (on_node_start, on_tool_end, etc.)
        # For now, call graph.run(task) directly.
        result = self.graph.run(task, **kwargs)
        self._log_event("terminate", {"result": result})

        # TODO: handle metrics and summary updates