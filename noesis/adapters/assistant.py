"""
Experimental OpenAI Assistants adapter for Noesis.

Contract:
- task in -> assistant run with tool calls (simulated here)
- respects IntuitionEvent patches
- logs events; surfaces NoesisVeto on blocking advice
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4
import json

from ..direction import DirectiveKind
from ..domain.artifacts.immutability import ArtifactWriteMode
from ..exceptions import NoesisVeto
from ..infrastructure.immutability import FinalizationSealStatus
from ..intuition import Intuition, IntuitionEvent
from ..usecases.immutability import ArtifactImmutabilityGuard
from .protocols import AdapterPath, DEFAULT_MIN_CONFIDENCE, STATE_HISTORY_LIMIT

__all__ = ["AssistantsAdapter"]

_EVENTS_FILE = "events.jsonl"
_FACULTY_PHASES: dict[str, str] = {
    "intuition": "intuition",
    "direction": "direction",
    "governance": "governance",
    "insight": "insight",
}
_VERB_PAYLOAD_MINIMA: dict[str, set[str]] = {
    "observe": {"task", "tags", "timestamp"},
    "interpret": {"signals"},
    "plan": {"steps"},
    "act": {"input_excerpt", "outcome"},
    "reflect": {"success"},
}
_ACTION_CANDIDATE_MINIMA: set[str] = {
    "action_candidate_id",
    "kind",
    "payload",
    "state_ref",
    "state_hash",
    "redaction",
}
_REQUIRED_EVENT_KEYS: set[str] = {
    "timestamp",
    "episode_id",
    "phase",
    "payload",
    "evidence_ids",
}
_EVENT_GUARD = ArtifactImmutabilityGuard(
    seal_status=FinalizationSealStatus(),
    append_only=frozenset({_EVENTS_FILE, "prompts.jsonl", "learn.jsonl"}),
)



def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()



def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None



def _last_event_timestamp(dir_path: Path) -> str | None:
    path = dir_path / _EVENTS_FILE
    if not path.exists():
        return None
    with path.open("rb") as handle:
        handle.seek(0, 2)
        end = handle.tell()
        if end == 0:
            return None
        buffer = bytearray()
        pos = end - 1
        while pos >= 0:
            handle.seek(pos)
            chunk = handle.read(1)
            if chunk == b"\n" and buffer:
                break
            if chunk != b"\n":
                buffer.extend(chunk)
            pos -= 1
        if not buffer:
            return None
        try:
            payload = json.loads(buffer[::-1].decode("utf-8"))
        except json.JSONDecodeError:
            return None
        ts = payload.get("timestamp")
        return ts if isinstance(ts, str) else None



def _normalize_event_timestamp(event: Dict[str, Any], *, last_timestamp: str | None) -> None:
    """
    Normalize event timestamps to ensure monotonic ordering.

    Rules:
    - If metrics.completed_at is present, event.timestamp must equal it.
    - Event timestamps must be >= the last emitted timestamp.
    """
    metrics = event.get("metrics")
    has_metrics = isinstance(metrics, dict)
    if has_metrics:
        completed_at = metrics.get("completed_at")
        if isinstance(completed_at, str):
            event["timestamp"] = completed_at
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("event.timestamp must be an ISO 8601 string")

    if last_timestamp:
        current = _parse_iso(timestamp)
        prior = _parse_iso(last_timestamp)
        if current is not None and prior is not None and current < prior:
            if has_metrics:
                raise ValueError(
                    f"event.timestamp {timestamp} is older than prior event timestamp {last_timestamp}"
                )
            event["timestamp"] = last_timestamp



def _validate_event_schema(event: Dict[str, Any]) -> None:
    """Light schema guard for adapter-written events."""
    missing = _REQUIRED_EVENT_KEYS - event.keys()
    if missing:
        raise ValueError(f"event missing required keys: {sorted(missing)}")

    if not isinstance(event.get("timestamp"), str):
        raise ValueError("event.timestamp must be str (ISO 8601)")
    if not isinstance(event.get("payload"), dict):
        raise ValueError("event.payload must be a dict")
    if not isinstance(event.get("evidence_ids"), list):
        raise ValueError("event.evidence_ids must be a list")

    caused_by = event.get("caused_by")
    if caused_by is not None and not isinstance(caused_by, str):
        raise ValueError("event.caused_by must be a string UUID when provided")

    metrics = event.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError("event.metrics must be a dict when provided")
        for key in ("started_at", "completed_at", "duration_ms"):
            if key not in metrics:
                raise ValueError(f"event.metrics is missing '{key}'")
        if not isinstance(metrics.get("duration_ms"), (int, float)):
            raise ValueError("event.metrics.duration_ms must be numeric")

    phase = event.get("phase")
    if isinstance(phase, str) and phase in _VERB_PAYLOAD_MINIMA:
        minima = _VERB_PAYLOAD_MINIMA.get(phase, set())
        payload_keys = set(event["payload"].keys())
        missing_payload = minima - payload_keys
        if missing_payload:
            raise ValueError(
                f"{phase} payload missing required keys: {sorted(missing_payload)}"
            )
        if phase == "act" and not {"tool", "adapter"} & payload_keys:
            raise ValueError("act payload requires either 'tool' or 'adapter'")

    if phase == "action_candidate":
        payload_keys = set(event["payload"].keys())
        missing_payload = _ACTION_CANDIDATE_MINIMA - payload_keys
        if missing_payload:
            raise ValueError(
                "action_candidate payload missing required keys: "
                f"{sorted(missing_payload)}"
            )

    faculty = event.get("faculty")
    if faculty is not None and not isinstance(faculty, str):
        raise ValueError("event.faculty must be a string when provided")
    if isinstance(faculty, str) and faculty not in _FACULTY_PHASES.values():
        raise ValueError(
            f"event.faculty must be one of {sorted(set(_FACULTY_PHASES.values()))}"
        )



def _canonical_event_dumps(value: Any) -> str:
    """Canonical JSON serializer aligned with runtime canonical_dumps."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )



def _append_event(
    run_dir: AdapterPath,
    *,
    episode_id: str,
    phase: str,
    agent_id: str,
    payload: Dict[str, Any],
) -> None:
    """Write an adapter event line with core safeguards preserved."""
    path = Path(run_dir)
    event = {
        "id": str(uuid4()),
        "timestamp": _ts(),
        "episode_id": episode_id,
        "agent_id": agent_id,
        "phase": phase,
        "payload": payload,
        "evidence_ids": [],
    }

    _normalize_event_timestamp(event, last_timestamp=_last_event_timestamp(path))
    if phase in _FACULTY_PHASES and "faculty" not in event:
        event["faculty"] = _FACULTY_PHASES[phase]
    _validate_event_schema(event)

    _EVENT_GUARD.ensure_write_allowed(
        episode_dir=path,
        artifact=_EVENTS_FILE,
        mode=ArtifactWriteMode.APPEND,
    )
    path.mkdir(parents=True, exist_ok=True)
    with (path / _EVENTS_FILE).open("a", encoding="utf-8") as handle:
        handle.write(_canonical_event_dumps(event) + "\n")


@dataclass
class _State:
    history: list
    tools_seen: list


class AssistantsAdapter:
    def __init__(
        self,
        assistant: Any,
        *,
        input_mapper=None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.assistant = assistant
        self.input_mapper = input_mapper or (lambda t: {"task": t})
        self._state = _State(history=[], tools_seen=[])
        self._min_conf = float(min_confidence)

    def _log(self, run_dir: AdapterPath, episode: str, phase: str, payload: Dict[str, Any]) -> None:
        _append_event(
            run_dir,
            episode_id=episode,
            phase=phase,
            agent_id="adapter.assistants",
            payload=payload,
        )
        if phase in {
            "intuition",
            "direction",
            "reason",
            "interpret",
            "plan",
            "act",
            "observe",
            "reflect",
            "error",
        }:
            self._state.history.append({"phase": phase, "payload": payload})
            if len(self._state.history) > STATE_HISTORY_LIMIT:
                del self._state.history[0]

    def _policy_tag(self, intuition: Optional[Intuition]) -> str:
        if not intuition:
            return "None"
        name = intuition.__class__.__name__
        version = (
            getattr(intuition, "__version__", None)
            or getattr(intuition, "version", None)
            or "unspecified"
        )
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
        run_dir: AdapterPath,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        policy = self._policy_tag(intuition)
        directive: Optional[IntuitionEvent] = None

        if intuition:
            directive = intuition.advise(
                {
                    "task": task,
                    "seed": seed,
                    "history": list(self._state.history),
                    "tools_seen": [],
                    "tags": tags or {},
                }
            )
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
                        "target": directive.target,
                        "scope": directive.scope,
                        "blocking": directive.blocking,
                        "patch_keys": sorted(directive.patch.keys()) if directive.patch else [],
                        "policy": policy,
                    },
                )

        self._log(run_dir, episode_id, "reason", {"note": "enter Assistants", "task": task})

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
                    raise NoesisVeto(
                        advice=directive.advice,
                        target=directive.target,
                        scope=directive.scope,
                    )

                if directive.kind == DirectiveKind.INTERVENTION.value:
                    patch = directive.patch or {}
                    if directive.confidence < self._min_conf:
                        payload.update(
                            {
                                "applied": False,
                                "patch": patch,
                                "reason": "policy_low_confidence",
                                "diff": [],
                            }
                        )
                        self._log(run_dir, episode_id, "direction", payload)
                    elif not patch:
                        payload.update(
                            {
                                "applied": False,
                                "patch": {},
                                "reason": "empty_patch",
                                "diff": [],
                            }
                        )
                        self._log(run_dir, episode_id, "direction", payload)
                    else:
                        adjusted, applied, diff, reason = self._apply_patch(input_obj, patch)
                        payload.update(
                            {
                                "applied": applied,
                                "patch": patch,
                                "reason": reason,
                                "diff": diff,
                            }
                        )
                        self._log(run_dir, episode_id, "direction", payload)
                        if applied:
                            input_obj = adjusted

            input_excerpt = str(input_obj)[:160]

            # (Simulated) assistants run; replace with real SDK call later
            result = {"assistant_reply": f"Processed task: {input_obj.get('task', str(input_obj))}"}
            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.assistants",
                    "input_excerpt": input_excerpt,
                    "outcome": str(result)[:400],
                },
            )
            return result

        except Exception as e:
            self._log(
                run_dir,
                episode_id,
                "act",
                {
                    "adapter": "adapter.assistants",
                    "input_excerpt": locals().get("input_excerpt", "<unset>"),
                    "outcome": "error",
                    "error": str(e),
                },
            )
            self._log(run_dir, episode_id, "error", {"message": str(e)})
            raise
