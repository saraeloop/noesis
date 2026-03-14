"""
Runtime event emission helpers.

Public facade replacing the legacy `_events` module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from noesis.trace.events import read_events, write_event

from .utils import now

__all__ = [
    "start_event",
    "observe_event",
    "interpret_event",
    "plan_event",
    "action_candidate_event",
    "act_event",
    "reflect_event",
    "direction_event",
    "governance_event",
    "runtime_lifecycle_event",
    "ensure_act_event",
    "terminate_event",
    "last_event_of_phase",
]


def start_event(
    run_dir: Path,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
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
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    ts = now_fn()
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
            "id": str(id_factory()),
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
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    payload: Dict[str, Any] = {"signals": signals}
    if reasons:
        payload["reasons"] = reasons
    payload["experimental"] = {"source": source}
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
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
    step_records: Optional[List[Dict[str, Any]]] = None,
    rationale: Optional[str] = None,
    source: str = "system",
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    payload: Dict[str, Any] = {"steps": steps}
    if step_records:
        payload["step_records"] = step_records
    if rationale:
        payload["rationale"] = rationale
    payload["source"] = source
    payload["experimental"] = {"source": source}
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
            "episode_id": episode_id,
            "agent_id": source,
            "phase": "plan",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def action_candidate_event(
    run_dir: Path,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    agent: str = "system",
    caused_by: Optional[str] = None,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> UUID:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    event_id = id_factory()
    record: Dict[str, Any] = {
        "id": str(event_id),
        "timestamp": now_fn(),
        "episode_id": episode_id,
        "agent_id": agent,
        "phase": "action_candidate",
        "payload": payload,
        "evidence_ids": [],
    }
    if caused_by:
        record["caused_by"] = caused_by
    write_event(run_dir, record)
    return event_id


def act_event(
    run_dir: Path,
    episode_id: str,
    *,
    adapter: Optional[str] = None,
    tool: Optional[str] = None,
    input_excerpt: str,
    outcome: str,
    step_status: Optional[str] = None,
    error: Optional[str] = None,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    payload: Dict[str, Any] = {
        "input_excerpt": input_excerpt,
        "outcome": outcome,
    }
    if adapter:
        payload["adapter"] = adapter
    if tool:
        payload["tool"] = tool
    if step_status:
        payload["step_status"] = step_status
    if error:
        payload["error"] = error
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
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
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    payload: Dict[str, Any] = {"success": success}
    if deltas:
        payload["deltas"] = deltas
    if reasons:
        payload["reasons"] = reasons
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "reflect",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def direction_event(
    run_dir: Path,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    agent: str = "system",
    evidence_ids: Optional[List[str]] = None,
    caused_by: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> UUID:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    event_id = id_factory()
    record: Dict[str, Any] = {
        "id": str(event_id),
        "timestamp": now_fn(),
        "episode_id": episode_id,
        "agent_id": agent,
        "phase": "direction",
        "payload": payload,
        "evidence_ids": list(evidence_ids or []),
    }
    if caused_by:
        record["caused_by"] = caused_by
    if metrics:
        record["metrics"] = metrics
    write_event(run_dir, record)
    return event_id


def governance_event(
    run_dir: Path,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    agent: str = "system",
    caused_by: Optional[str] = None,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> UUID:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    event_id = id_factory()
    record: Dict[str, Any] = {
        "id": str(event_id),
        "timestamp": now_fn(),
        "episode_id": episode_id,
        "agent_id": agent,
        "phase": "governance",
        "payload": payload,
        "evidence_ids": [],
    }
    if caused_by:
        record["caused_by"] = caused_by
    write_event(run_dir, record)
    return event_id


def runtime_lifecycle_event(
    run_dir: Path,
    episode_id: str,
    *,
    event_type: str,
    payload: Dict[str, Any],
    agent: str = "system",
    caused_by: Optional[str] = None,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> UUID:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    event_id = id_factory()
    record: Dict[str, Any] = {
        "id": str(event_id),
        "timestamp": now_fn(),
        "episode_id": episode_id,
        "agent_id": agent,
        "event_type": event_type,
        "phase": "runtime",
        "payload": payload,
        "evidence_ids": [],
    }
    if caused_by:
        record["caused_by"] = caused_by
    write_event(run_dir, record)
    return event_id


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


def terminate_event(
    run_dir: Path,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], UUID] | None = None,
) -> None:
    now_fn = now_fn or now
    id_factory = id_factory or uuid4
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
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
