from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..trace.events import read_events, write_event
from ._utils import now

__all__ = [
    "start_event",
    "observe_event",
    "interpret_event",
    "plan_event",
    "act_event",
    "reflect_event",
    "ensure_act_event",
    "terminate_event",
    "last_event_of_phase",
]


def start_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def observe_event(
    run_dir: Path,
    episode_id: str,
    *,
    task: str,
    tags: Optional[Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
) -> None:
    ts = now()
    payload: Dict[str, Any] = {
        "task": task,
        "tags": tags or {},
        "timestamp": ts,
    }
    if snapshot:
        payload["experimental"] = {"snapshot": snapshot}
    write_event(
        run_dir,
        {
            "timestamp": ts,
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "observe",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def interpret_event(
    run_dir: Path,
    episode_id: str,
    *,
    signals: List[str],
    reasons: Optional[List[str]] = None,
    source: str = "system",
) -> None:
    payload: Dict[str, Any] = {"signals": signals}
    if reasons:
        payload["reasons"] = reasons
    payload["experimental"] = {"source": source}
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": source,
            "phase": "interpret",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def plan_event(
    run_dir: Path,
    episode_id: str,
    *,
    steps: List[str],
    rationale: Optional[str] = None,
    source: str = "system",
) -> None:
    payload: Dict[str, Any] = {"steps": steps}
    if rationale:
        payload["rationale"] = rationale
    payload["experimental"] = {"source": source}
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": source,
            "phase": "plan",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def act_event(
    run_dir: Path,
    episode_id: str,
    *,
    adapter: Optional[str] = None,
    tool: Optional[str] = None,
    input_excerpt: str,
    outcome: str,
    error: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "input_excerpt": input_excerpt,
        "outcome": outcome,
    }
    if adapter:
        payload["adapter"] = adapter
    if tool:
        payload["tool"] = tool
    if error:
        payload["error"] = error
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": adapter or tool or "system",
            "phase": "act",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def reflect_event(
    run_dir: Path,
    episode_id: str,
    *,
    success: bool,
    deltas: Optional[List[str]] = None,
    reasons: Optional[List[str]] = None,
) -> None:
    payload: Dict[str, Any] = {"success": success}
    if deltas:
        payload["deltas"] = deltas
    if reasons:
        payload["reasons"] = reasons
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "reflect",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def ensure_act_event(
    run_dir: Path,
    episode_id: str,
    *,
    adapter_label: str,
    input_excerpt: str,
    outcome: str,
) -> None:
    events = read_events(run_dir)
    if any(evt.get("phase") == "act" for evt in events):
        return
    act_event(
        run_dir,
        episode_id,
        adapter=adapter_label,
        input_excerpt=input_excerpt,
        outcome=outcome,
    )


def terminate_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "terminate",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def last_event_of_phase(events: List[Dict[str, Any]], phase: str) -> Optional[Dict[str, Any]]:
    for event in reversed(events):
        if event.get("phase") == phase:
            return event
    return None
