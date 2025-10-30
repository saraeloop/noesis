"""
LangGraph adapter for Noēsis.

Bridges LangGraph executions into the Noēsis cognitive loop,
translating node-level reasoning into structured events and
policy-aware interventions.

Purpose
--------
- Acts as a runtime bridge between LangGraph graphs and the Noēsis
  trace, intuition, and direction layers.
- Captures every reasoning phase ("intuition", "reason", "direction",
  "observe", "terminate") as normalized events.
- Applies DirectedIntuition patches and vetoes in-line with
  confidence thresholds and schema-consistent diffs.
- Ensures every LangGraph run produces a complete, analyzable
  trace and summary regardless of outcome.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol
from copy import deepcopy
from os import PathLike

from ..trace.events import write_event
from ..intuition import Intuition, IntuitionEvent
from ..direction import DirectiveKind
from ..exceptions import NoesisVeto

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

    def append_history(self, phase: str, payload: Dict[str, Any]) -> None:
        if phase in {
            "intuition",
            "direction",
            "reason",
            "observe",
            "interpret",
            "plan",
            "act",
            "reflect",
            "error",
        }:
            self.history.append({"phase": phase, "payload": payload})
            if len(self.history) > 50:
                del self.history[0]

    def note_tool(self, payload: Dict[str, Any]) -> None:
        tool_name = payload.get("tool")
        if tool_name and tool_name not in self.tools_seen:
            self.tools_seen.append(tool_name)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _excerpt(obj: Any, limit: int = 400) -> str:
    """
    Safe string excerpt from typical LangChain/LangGraph returns:
    - BaseMessage / AIMessage (uses `.content` if present)
    - dict-like (pretty-safe str)
    - anything else -> str(obj)
    """
    try:
        if hasattr(obj, "content"):
            s = str(getattr(obj, "content"))
        else:
            s = str(obj)
    except Exception:
        s = "<unprintable result>"
    return (s[:limit]) if len(s) > limit else s


class LangGraphAdapter:
    """
    Wrap a LangGraph graph to emit Noēsis-compatible events and apply intuition.

    Resolution order:
      1) `graph.invoke(input)` (typical for compiled graphs)
      2) `graph.run(input)`    (older/simple APIs)
      3) callable(graph)(input)

    Input mapping:
      - If your graph expects a dict (e.g., {"task": ...}), provide an `input_mapper`
        or set `graph.__noesis_input_mapper__ = lambda s: {"task": s}`.
        The explicit constructor argument takes precedence over the attribute.
    """

    def __init__(self, graph: Any, *, input_mapper: Optional[Callable[[str], Any]] = None, min_confidence: float = 0.5) -> None:
        self.graph = graph
        # precedence: explicit arg > graph attribute > identity
        discovered = getattr(graph, "__noesis_input_mapper__", None)
        self.input_mapper: Callable[[str], Any] = input_mapper or discovered or (lambda t: t)
        self._state = _State(history=[], tools_seen=[])
        self._min_confidence = float(min_confidence)

    def _log(self, run_dir: PathLike[str] | str, episode_id: str, phase: str, payload: Dict[str, Any]) -> None:
        body = {
            "timestamp": _ts(),
            "episode_id": episode_id,
            "agent_id": "adapter.langgraph",
            "phase": phase,
            "payload": payload,
            "evidence_ids": payload.get("evidence_ids", []),
        }
        write_event(run_dir, body)
        self._state.append_history(phase, payload)
        self._state.note_tool(payload)

    @staticmethod
    def _policy_tag(intuition: Optional[Intuition]) -> str:
        if intuition is None:
            return "None"
        name = intuition.__class__.__name__
        version = getattr(intuition, "__version__", None) or getattr(intuition, "version", None) or "unspecified"
        return f"{name}@{version}"

    def _snapshot(self, *, task: str, seed: int, tags: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "task": task,
            "seed": seed,
            "history": list(self._state.history),
            "tools_seen": list(self._state.tools_seen),
            "tags": tags or {},
        }

    def _apply_patch(
        self,
        input_obj: Any,
        patch: Dict[str, Any],
    ) -> tuple[Any, bool, list[Dict[str, Any]], str]:
        if isinstance(input_obj, dict):
            updated = deepcopy(input_obj)
            diff: list[Dict[str, Any]] = []
            for key, value in patch.items():
                before = input_obj.get(key)
                diff.append({"key": key, "before": before, "after": value})
                updated[key] = value
            return updated, True, diff, "applied"

        if isinstance(input_obj, str) and "rewrite" in patch:
            rewritten = str(patch["rewrite"])
            diff = [{"key": "rewrite", "before": input_obj, "after": rewritten}]
            return rewritten, True, diff, "rewritten"

        return input_obj, False, [], "not_patchable_input"

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
        directive: Optional[IntuitionEvent] = None
        # Pre-run advisory (core already logs "start"; this is adapter-level hinting)
        policy_tag = self._policy_tag(intuition)

        if intuition:
            directive = intuition.advise(self._snapshot(task=task, seed=seed, tags=tags))
            if directive:
                self._log(
                    run_dir,
                    episode_id,
                    "intuition",
                    {
                        "kind": directive.kind,
                        "advice": directive.advice,
                        "confidence": directive.confidence,
                        "applied": directive.applied,
                        "rationale": directive.rationale,
                        "evidence_ids": directive.evidence_ids,
                        "target": directive.target,
                        "scope": directive.scope,
                        "blocking": directive.blocking,
                        "patch_keys": sorted(directive.patch.keys()) if directive.patch else [],
                        "policy": policy_tag,
                    },
                )

        # Execution boundary
        self._log(run_dir, episode_id, "reason", {"note": "enter LangGraph", "task": task})

        try:
            input_obj = self.input_mapper(task)

            if directive:
                input_obj = self._enforce_direction(
                    directive,
                    input_obj,
                    run_dir,
                    episode_id,
                    policy_tag,
                )

            input_excerpt = _excerpt(input_obj)

            if hasattr(self.graph, "invoke"):
                result = self.graph.invoke(input_obj)  # compiled LangGraph
            elif hasattr(self.graph, "run"):
                result = self.graph.run(input_obj)     # older/simple APIs
            elif callable(self.graph):
                result = self.graph(input_obj)         # fallback
            else:
                raise TypeError("graph object is neither runnable (.invoke/.run) nor callable")

            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.langgraph",
                    "input_excerpt": input_excerpt,
                    "outcome": _excerpt(result),
                },
            )
            return result

        except Exception as e:
            # Failure boundary
            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.langgraph",
                    "input_excerpt": locals().get("input_excerpt", "<unset>"),
                    "outcome": "error",
                    "error": str(e),
                },
            )
            self._log(run_dir, episode_id, "error", {"message": str(e)})
            raise

    def _enforce_direction(
        self,
        directive: IntuitionEvent,
        input_obj: Any,
        run_dir: PathLike[str] | str,
        episode_id: str,
        policy_tag: str,
    ) -> Any:
        kind = directive.kind
        payload: Dict[str, Any] = {
            "kind": kind,
            "advice": directive.advice,
            "confidence": directive.confidence,
            "target": directive.target,
            "scope": directive.scope,
            "policy": policy_tag,
            "threshold": self._min_confidence,
        }

        if directive.blocking or kind == DirectiveKind.VETO.value:
            payload.update({"applied": False, "status": "blocked", "reason": "veto"})
            self._log(run_dir, episode_id, "direction", payload)
            directive.applied = False
            raise NoesisVeto(advice=directive.advice, target=directive.target, scope=directive.scope)

        if kind == DirectiveKind.INTERVENTION.value:
            patch = directive.patch or {}

            if directive.confidence < self._min_confidence:
                payload.update({
                    "applied": False,
                    "patch": patch,
                    "reason": "policy_low_confidence",
                    "diff": [],
                })
                directive.applied = False
                self._log(run_dir, episode_id, "direction", payload)
                return input_obj

            if not patch:
                payload.update({
                    "applied": False,
                    "patch": {},
                    "reason": "empty_patch",
                    "diff": [],
                })
                directive.applied = False
                self._log(run_dir, episode_id, "direction", payload)
                return input_obj

            adjusted, applied, diff, reason = self._apply_patch(input_obj, patch)
            payload.update({
                "applied": applied,
                "patch": patch,
                "reason": reason,
                "diff": diff,
            })
            directive.applied = applied
            self._log(run_dir, episode_id, "direction", payload)
            if applied:
                return adjusted
            return input_obj

        # Hints are advisory only; they already logged via the intuition phase.
        return input_obj
