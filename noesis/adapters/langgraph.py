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
import asyncio
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from copy import deepcopy
from uuid import UUID

from ..intuition import Intuition, IntuitionEvent
from ..direction import DirectiveKind
from ..exceptions import NoesisVeto
from .protocols import (
    AdapterPath,
    Executor,
    DEFAULT_MIN_CONFIDENCE,
)
from ..domain.state.cognitive import CognitiveEvent, CognitiveMetrics, CognitiveVerb, LineageTracker
from ..runtime.clock import RuntimeClock, PhaseToken
from ..runtime.events_emitter import CognitiveEventEmitter
from ..runtime.utils import now as runtime_now
from .. import events as public_events

__all__ = ["LangGraphAdapter", "Executor"]


@dataclass(slots=True)
class _State:
    """Adapter-local snapshot used for advisory hooks."""

    tools_seen: set[str]

    def note_tool(self, tool_name: str | None) -> None:
        if tool_name:
            self.tools_seen.add(tool_name)

    def snapshot(self) -> Dict[str, Any]:
        return {"tools_seen": sorted(self.tools_seen)}
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

    def __init__(
        self,
        graph: Any,
        *,
        input_mapper: Optional[Callable[[str], Any]] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.graph = graph
        # precedence: explicit arg > graph attribute > identity
        discovered = getattr(graph, "__noesis_input_mapper__", None)
        self.input_mapper: Callable[[str], Any] = input_mapper or discovered or (lambda t: t)
        self._state = _State(tools_seen=set())
        self._min_confidence = float(min_confidence)
        self._clock = RuntimeClock()
        self._lineage = LineageTracker()
        self._current_episode: Optional[str] = None

    def _reset(self, episode_id: str) -> None:
        self._state = _State(tools_seen=set())
        self._clock = RuntimeClock()
        self._lineage = LineageTracker()
        self._current_episode = episode_id

    @staticmethod
    def _policy_tag(intuition: Optional[Intuition]) -> str:
        if intuition is None:
            return "None"
        name = intuition.__class__.__name__
        version = getattr(intuition, "__version__", None) or getattr(intuition, "version", None) or "unspecified"
        return f"{name}@{version}"

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

    def _start_phase(self, verb: CognitiveVerb) -> PhaseToken:
        return self._clock.start(verb)

    def _stop_phase(self, token: PhaseToken) -> CognitiveMetrics:
        return self._clock.stop(token)

    def _emit_event(
        self,
        emitter: CognitiveEventEmitter,
        verb: CognitiveVerb,
        payload: Dict[str, Any],
        *,
        agent_id: str = "adapter.langgraph",
        cause: Optional[UUID] = None,
        metrics: Optional[CognitiveMetrics] = None,
    ) -> UUID:
        event = CognitiveEvent(
            episode_id=self._current_episode or "",
            verb=verb,
            payload=payload,
        )
        if metrics is not None:
            event = event.with_metrics(metrics)
        linked = self._lineage.register(event, cause=cause)
        emitter.emit(linked, agent_id=agent_id)
        return linked.event_id

    def _record_instant(
        self,
        emitter: CognitiveEventEmitter,
        verb: CognitiveVerb,
        payload: Dict[str, Any],
        *,
        agent_id: str = "adapter.langgraph",
        cause: Optional[UUID] = None,
    ) -> UUID:
        token = self._start_phase(verb)
        metrics = self._stop_phase(token)
        return self._emit_event(
            emitter,
            verb,
            payload,
            agent_id=agent_id,
            cause=cause,
            metrics=metrics,
        )

    def _emit_plan_with_direction(
        self,
        emitter: CognitiveEventEmitter,
        payload: Dict[str, Any],
        *,
        cause: Optional[UUID],
        run_dir: Path,
    ) -> UUID:
        token = self._start_phase(CognitiveVerb.PLAN)
        metrics = self._stop_phase(token)
        plan_event_id = self._emit_event(
            emitter,
            CognitiveVerb.PLAN,
            payload,
            cause=cause,
            metrics=metrics,
        )
        public_events.direction(
            run_dir,
            self._current_episode or "",
            payload.copy(),
            agent="adapter.langgraph",
            caused_by=str(plan_event_id),
            metrics=metrics.to_dict(),
        )
        return plan_event_id

    @staticmethod
    def _categorize_error(exc: Exception) -> str:
        name = exc.__class__.__name__
        if isinstance(exc, TimeoutError):
            return "timeout"
        lowered = name.lower()
        if "tool" in lowered:
            return "tool_failure"
        if "state" in lowered:
            return "invalid_state"
        return name

    def _extract_tools(self, result: Any) -> list[str]:
        names: set[str] = set()
        tool_calls = getattr(result, "tool_calls", None)
        if isinstance(tool_calls, list):
            for call in tool_calls:
                name = None
                if isinstance(call, dict):
                    name = call.get("name")
                else:
                    name = getattr(call, "name", None)
                if name:
                    names.add(str(name))
        if isinstance(result, dict):
            maybe_tool = result.get("tool") or result.get("tool_name")
            if maybe_tool:
                names.add(str(maybe_tool))
            calls = result.get("tool_calls")
            if isinstance(calls, list):
                for call in calls:
                    if isinstance(call, dict):
                        name = call.get("name")
                        if name:
                            names.add(str(name))
        for name in names:
            self._state.note_tool(name)
        return sorted(names)

    def _await_maybe_async(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return self._run_coroutine(value)
        return value

    def _run_coroutine(self, coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        if not loop.is_running():
            return loop.run_until_complete(coro)  # pragma: no cover - legacy loop usage
        # Running loop: execute in a dedicated new loop to avoid blocking.
        new_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            try:
                asyncio.set_event_loop(loop)
            except Exception:
                asyncio.set_event_loop(None)

    def _invoke_graph(self, input_obj: Any) -> Any:
        graph = self.graph
        if hasattr(graph, "invoke"):
            value = graph.invoke(input_obj)
        elif hasattr(graph, "ainvoke"):
            value = graph.ainvoke(input_obj)
        elif hasattr(graph, "run"):
            value = graph.run(input_obj)
        elif hasattr(graph, "arun"):
            value = graph.arun(input_obj)
        elif callable(graph):
            value = graph(input_obj)
        else:
            raise TypeError("graph object is neither runnable (.invoke/.run) nor callable")
        return self._await_maybe_async(value)
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
        tags = tags or {}
        run_path = Path(run_dir)
        self._reset(episode_id)
        emitter = CognitiveEventEmitter(run_dir=run_path, agent_id="adapter.langgraph")

        observe_payload = {"task": task, "tags": tags, "timestamp": runtime_now()}
        observe_id = self._record_instant(emitter, CognitiveVerb.OBSERVE, observe_payload)
        cause_id: Optional[UUID] = observe_id

        policy_tag = self._policy_tag(intuition)

        interpret_token = self._start_phase(CognitiveVerb.INTERPRET)
        input_obj = self.input_mapper(task)
        directive: Optional[IntuitionEvent] = None
        if intuition:
            advisory_snapshot = {
                "task": task,
                "seed": seed,
                "tags": tags,
                **self._state.snapshot(),
            }
            directive = intuition.advise(advisory_snapshot)
        interpret_payload: Dict[str, Any] = {
            "policy": policy_tag,
            "input_type": type(input_obj).__name__,
            "kind": directive.kind if directive else "none",
            "confidence": directive.confidence if directive else None,
            "blocking": directive.blocking if directive else False,
            "target": directive.target if directive else None,
            "scope": directive.scope if directive else None,
            "signals": [f"input:{type(input_obj).__name__}"],
        }
        if directive and directive.advice:
            interpret_payload["advice"] = directive.advice
        if directive and directive.patch:
            interpret_payload["patch_keys"] = sorted(directive.patch.keys())
        interpret_metrics = self._stop_phase(interpret_token)
        interpret_id = self._emit_event(
            emitter,
            CognitiveVerb.INTERPRET,
            interpret_payload,
            cause=cause_id,
            metrics=interpret_metrics,
        )
        cause_id = interpret_id

        plan_event_id: Optional[UUID] = None
        if directive:
            directive_kind = directive.kind or ""
            policy_version = policy_tag.split("@", 1)[1] if "@" in policy_tag else "unspecified"
            payload: Dict[str, Any] = {
                "policy": policy_tag,
                "policy_version": policy_version,
                "kind": directive_kind,
                "confidence": directive.confidence,
                "threshold": self._min_confidence,
                "target": directive.target,
                "scope": directive.scope,
                "steps": ["apply_directive"],
                "applied": False,
                "diff": [],
            }
            if directive.blocking or directive_kind == DirectiveKind.VETO.value:
                payload.update({"status": "blocked", "reason": "veto", "steps": ["directive_veto"], "applied": False})
                plan_event_id = self._emit_plan_with_direction(
                    emitter,
                    payload,
                    cause=cause_id,
                    run_dir=run_path,
                )
                self._lineage.seed(last_event_id=plan_event_id)
                raise NoesisVeto(advice=directive.advice, target=directive.target, scope=directive.scope)

            if directive_kind == DirectiveKind.INTERVENTION.value:
                patch = directive.patch or {}
                if directive.confidence < self._min_confidence:
                    payload.update(
                        {
                            "status": "skipped",
                            "reason": "policy_low_confidence",
                            "patch": patch,
                            "steps": ["directive_skipped"],
                            "applied": False,
                        }
                    )
                    plan_event_id = self._emit_plan_with_direction(
                        emitter,
                        payload,
                        cause=cause_id,
                        run_dir=run_path,
                    )
                    directive.applied = False
                elif not patch:
                    payload.update(
                        {
                            "status": "skipped",
                            "reason": "empty_patch",
                            "patch": {},
                            "steps": ["directive_skipped"],
                            "applied": False,
                        }
                    )
                    plan_event_id = self._emit_plan_with_direction(
                        emitter,
                        payload,
                        cause=cause_id,
                        run_dir=run_path,
                    )
                    directive.applied = False
                else:
                    adjusted, applied, diff, reason = self._apply_patch(input_obj, patch)
                    payload.update(
                        {
                            "status": "applied" if applied else "skipped",
                            "reason": reason,
                            "patch": patch,
                            "diff": diff,
                            "applied": applied,
                        }
                    )
                    plan_event_id = self._emit_plan_with_direction(
                        emitter,
                        payload,
                        cause=cause_id,
                        run_dir=run_path,
                    )
                    if applied:
                        directive.applied = True
                        input_obj = adjusted
                    else:
                        directive.applied = False
            else:
                payload.update({"status": "hint", "reason": "hint", "steps": ["directive_hint"], "applied": False})
                plan_event_id = self._emit_plan_with_direction(
                    emitter,
                    payload,
                    cause=cause_id,
                    run_dir=run_path,
                )
                directive.applied = False
            cause_id = plan_event_id or cause_id

        if plan_event_id is None:
            default_plan_payload = {
                "steps": [f"invoke:{self.graph.__class__.__name__}"]
            }
            plan_event_id = self._record_instant(
                emitter,
                CognitiveVerb.PLAN,
                default_plan_payload,
                cause=cause_id,
            )
            cause_id = plan_event_id

        input_excerpt = _excerpt(input_obj)
        act_token = self._start_phase(CognitiveVerb.ACT)
        try:
            result = self._invoke_graph(input_obj)
            metrics = self._stop_phase(act_token)
            tools_used = self._extract_tools(result)
            act_payload = {
                "adapter": "adapter.langgraph",
                "input_excerpt": input_excerpt,
                "outcome": "ok",
                "tools": tools_used,
            }
            act_id = self._emit_event(
                emitter,
                CognitiveVerb.ACT,
                act_payload,
                cause=cause_id,
                metrics=metrics,
            )
            reflect_payload = {
                "success": True,
                "reasons": ["graph_completed"],
            }
            reflect_id = self._record_instant(
                emitter,
                CognitiveVerb.REFLECT,
                reflect_payload,
                cause=act_id,
            )
            return result
        except Exception as exc:
            metrics = self._stop_phase(act_token)
            tools_used = sorted(self._state.tools_seen)
            act_payload = {
                "adapter": "adapter.langgraph",
                "input_excerpt": input_excerpt,
                "outcome": "error",
                "error": str(exc)[:256],
                "error_kind": self._categorize_error(exc),
                "tools": tools_used,
            }
            act_id = self._emit_event(
                emitter,
                CognitiveVerb.ACT,
                act_payload,
                cause=cause_id,
                metrics=metrics,
            )
            reflect_payload = {
                "success": False,
                "reasons": [self._categorize_error(exc)],
            }
            self._record_instant(
                emitter,
                CognitiveVerb.REFLECT,
                reflect_payload,
                cause=act_id,
            )
            raise
