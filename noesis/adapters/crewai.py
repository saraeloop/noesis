"""
Experimental CrewAI adapter for Noēsis.

Contract:
- task in → plan/steps (simulated here)
- respects IntuitionEvent patches (input dict only)
- logs phases and surfaces veto via NoesisVeto
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from os import PathLike
from copy import deepcopy
from ..trace.events import write_event
from ..intuition import Intuition, IntuitionEvent
from ..direction import DirectiveKind
from ..exceptions import NoesisVeto
from datetime import datetime, timezone

__all__ = ["CrewAIAdapter"]

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class _State:
    history: list
    tools_seen: list

class CrewAIAdapter:
    def __init__(self, crew: Any, *, input_mapper=None, min_confidence: float = 0.5) -> None:
        self.crew = crew
        self.input_mapper = input_mapper or (lambda t: {"task": t})
        self._state = _State(history=[], tools_seen=[])
        self._min_conf = float(min_confidence)

    def _log(self, run_dir: PathLike[str] | str, episode: str, phase: str, payload: Dict[str, Any]) -> None:
        write_event(run_dir, {"timestamp": _ts(), "episode_id": episode, "agent_id": "adapter.crewai", "phase": phase, "payload": payload, "evidence_ids": []})
        if phase in {"intuition", "direction", "reason", "interpret", "plan", "act", "observe", "reflect", "error"}:
            self._state.history.append({"phase": phase, "payload": payload})
            if len(self._state.history) > 50:
                del self._state.history[0]

    def _policy_tag(self, intuition: Optional[Intuition]) -> str:
        if not intuition: return "None"
        name = intuition.__class__.__name__
        version = getattr(intuition, "__version__", None) or getattr(intuition, "version", None) or "unspecified"
        return f"{name}@{version}"

    def _apply_patch(self, inp: Any, patch: Dict[str, Any]):
        if not isinstance(inp, dict):
            return inp, False, [], "not_dict_input"
        out = deepcopy(inp)
        diff = []
        for k, v in patch.items():
            diff.append({"key": k, "before": out.get(k), "after": v})
            out[k] = v
        return out, True, diff, "applied"

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
        # Pre
        policy = self._policy_tag(intuition)
        directive: Optional[IntuitionEvent] = None
        if intuition:
            directive = intuition.advise({"task": task, "seed": seed, "history": list(self._state.history), "tools_seen": [], "tags": tags or {}})
            if directive:
                self._log(run_dir, episode_id, "intuition", {
                    "kind": directive.kind, "advice": directive.advice, "confidence": directive.confidence,
                    "applied": directive.applied, "rationale": directive.rationale,
                    "target": directive.target, "scope": directive.scope, "blocking": directive.blocking,
                    "patch_keys": sorted(directive.patch.keys()) if directive.patch else [],
                    "policy": policy
                })
        self._log(run_dir, episode_id, "reason", {"note": "enter CrewAI", "task": task})

        try:
            input_obj = self.input_mapper(task)

            if directive:
                payload = {
                    "kind": directive.kind,
                    "advice": directive.advice,
                    "confidence": directive.confidence,
                    "target": directive.target,
                    "scope": directive.scope,
                    "policy": policy,
                    "threshold": self._min_conf,
                }
                if directive.blocking or directive.kind == DirectiveKind.VETO.value:
                    payload.update({"applied": False, "status": "blocked", "reason": "veto"})
                    self._log(run_dir, episode_id, "direction", payload)
                    raise NoesisVeto(advice=directive.advice, target=directive.target, scope=directive.scope)

                if directive.kind == DirectiveKind.INTERVENTION.value:
                    patch = directive.patch or {}
                    if directive.confidence < self._min_conf:
                        payload.update({"applied": False, "patch": patch, "reason": "policy_low_confidence", "diff": []})
                        self._log(run_dir, episode_id, "direction", payload)
                    elif not patch:
                        payload.update({"applied": False, "patch": {}, "reason": "empty_patch", "diff": []})
                        self._log(run_dir, episode_id, "direction", payload)
                    else:
                        adjusted, applied, diff, reason = self._apply_patch(input_obj, patch)
                        payload.update({"applied": applied, "patch": patch, "reason": reason, "diff": diff})
                        self._log(run_dir, episode_id, "direction", payload)
                        if applied:
                            input_obj = adjusted

            input_excerpt = str(input_obj)[:160]

            # (Simulated) crew.run → plan/steps
            # Replace with real CrewAI call later.
            plan = [
                {"step": 1, "action": "gather_requirements"},
                {"step": 2, "action": "draft_plan"},
                {"step": 3, "action": "review_with_user"},
            ]
            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.crewai",
                    "input_excerpt": input_excerpt,
                    "outcome": f"plan({len(plan)} steps)",
                },
            )
            return plan

        except Exception as e:
            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.crewai",
                    "input_excerpt": locals().get("input_excerpt", "<unset>"),
                    "outcome": "error",
                    "error": str(e),
                },
            )
            self._log(run_dir, episode_id, "error", {"message": str(e)})
            raise
