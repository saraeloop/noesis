"""
Runtime learning helpers.

Owns learning persistence helpers so runtime does not depend on public facades.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
from collections import Counter
from datetime import datetime, timezone

from noesis.interfaces.config import ConfigSnapshot
from noesis.domain.learning.model import (
    LearnMode,
    LearnProposal,
    LearnStatus,
    derive_target_key,
)
from noesis.trace.events import write_event

from .config_provider import get_config_port
from .events import last_event_of_phase
from .utils import now

__all__ = [
    "LearnMode",
    "LearnStatus",
    "LearnProposal",
    "build_learn_payload",
    "persist_episode_learning",
    "load_policy_snapshot",
    "update_policy_snapshot",
    "derive_target_key",
    "summarise_learn_kinds",
    "maybe_emit_learn_event",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_policy_id(policy_id: str) -> str:
    return policy_id.replace("/", "_").replace(" ", "_")


def build_learn_payload(
    *,
    policy_id: str | None,
    metrics: Dict[str, Any],
    reasons: Iterable[str],
    latencies: Dict[str, Any],
    counts: Dict[str, int],
    proposals: List[LearnProposal],
    applied: bool,
    scope: str = "policy",
    ttl: Any = None,
    proposal_id: Optional[str] = None,
    approval: str = "pending",
) -> Dict[str, Any]:
    return {
        "id": proposal_id,
        "policy_id": policy_id,
        "basis": {
            "success": metrics.get("success"),
            "reasons": list(reasons),
            "latencies": latencies,
            "counts": counts,
        },
        "proposal": [p.to_dict() for p in proposals],
        "applied": applied,
        "scope": scope,
        "ttl": ttl,
        "approval": approval,
    }


def persist_episode_learning(run_dir: Path, payload: Dict[str, Any]) -> None:
    path = run_dir / "learn.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": _now(), "payload": payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_policy_snapshot(learn_home: Path, policy_id: str) -> Dict[str, Any]:
    policies_dir = learn_home / "policies"
    snapshot_path = policies_dir / f"{_sanitize_policy_id(policy_id)}.json"
    if snapshot_path.exists():
        with snapshot_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "policy_id": policy_id,
        "tuning": {},
        "stats": {"episodes": 0},
        "history": [],
        "gates": {},
    }


def update_policy_snapshot(
    learn_home: Path,
    policy_id: str,
    proposals: List[Dict[str, Any]],
    *,
    gate_updates: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    if not policy_id:
        return
    policies_dir = learn_home / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = policies_dir / f"{_sanitize_policy_id(policy_id)}.json"

    snapshot = load_policy_snapshot(learn_home, policy_id)
    snapshot["updated_at"] = _now()
    stats = snapshot.setdefault("stats", {})
    stats["episodes"] = int(stats.get("episodes", 0)) + 1

    history = snapshot.setdefault("history", [])
    tuning = snapshot.setdefault("tuning", {})
    gates = snapshot.setdefault("gates", {})

    for item in proposals:
        target = item.get("target", {})
        path = target.get("path")
        status = item.get("status")
        history.append(
            {
                "ts": _now(),
                "proposal_id": item.get("proposal_id"),
                "kind": item.get("kind"),
                "target": target,
                "score": item.get("score"),
                "confidence": item.get("confidence"),
                "status": status,
                "revert_handle": item.get("revert_handle"),
            }
        )
        if status == LearnStatus.APPLIED.value and item.get("accepted") and path:
            tuning[path] = target.get("to")

    if gate_updates:
        for key, info in gate_updates.items():
            gates.setdefault(key, {}).update(info)

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def summarise_learn_kinds(proposals: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(p.get("kind", "unknown") for p in proposals)
    return dict(counts)


def maybe_emit_learn_event(
    *,
    run_dir: Path,
    episode_id: str,
    events: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    config: ConfigSnapshot,
) -> Optional[Dict[str, Any]]:
    mode = config.learn_mode
    if mode is LearnMode.OFF:
        return None

    direction_event = last_event_of_phase(events, "direction")
    policy_id = (direction_event or {}).get("payload", {}).get("policy")
    if not policy_id:
        return None

    policy_version = (direction_event or {}).get("payload", {}).get("policy_version")
    reflect_event = last_event_of_phase(events, "reflect") or {}
    reasons = reflect_event.get("payload", {}).get("reasons", []) or []

    latencies = metrics.get("latencies", {}) or {}
    counts = {
        "plan": metrics.get("plan_count", 0),
        "act": metrics.get("steps", 0),
        "reflect": metrics.get("reflect_count", 0),
    }

    proposals: List[LearnProposal] = []
    direction_vetoed = metrics.get("direction_vetoed", 0)
    current_threshold = float(config.direction_min_confidence)
    if direction_vetoed:
        proposed_threshold = min(1.0, round(current_threshold + 0.05, 2))
        if proposed_threshold > current_threshold:
            proposal = LearnProposal(
                proposal_id=f"{policy_id}:{episode_id}:direction_min_confidence:{proposed_threshold}",
                policy_id=policy_id,
                policy_version=policy_version,
                kind="threshold_tune",
                target={
                    "path": "direction_min_confidence",
                    "from": current_threshold,
                    "to": proposed_threshold,
                },
                rationale="Increase direction minimum confidence after veto.",
                evidence_ids=[episode_id],
                score_fn="heuristic:veto_rate",
            )
            proposals.append(proposal)

    applied_any = False
    gate_updates: Dict[str, Dict[str, Any]] = {}
    proposal_dicts: List[Dict[str, Any]] = []

    learn_home = config.learn_home.expanduser()

    if proposals:
        learn_home.mkdir(parents=True, exist_ok=True)
        policy_snapshot = load_policy_snapshot(learn_home, policy_id)

        min_conf = float(config.learn_auto_apply_min_confidence)
        min_successes = int(config.learn_auto_apply_min_successes)

        total_direction_events = max(metrics.get("direction_events", 0), 1)
        veto_rate = direction_vetoed / total_direction_events

        for proposal in proposals:
            if proposal.kind == "threshold_tune":
                proposal.metadata["veto_rate"] = veto_rate
                proposal.metadata["direction_events"] = total_direction_events
                proposal.mark_scored(score=veto_rate, confidence=min(1.0, veto_rate), scorer="heuristic:veto_rate")

            gate_key = derive_target_key(proposal.target, fallback=proposal.kind)
            gate_state = policy_snapshot.get("gates", {}).get(gate_key, {})
            successes = int(gate_state.get("successes", 0))

            if proposal.confidence >= min_conf:
                successes += 1
                proposal.approve()
            else:
                successes = 0

            if mode is LearnMode.APPLY and proposal.status == LearnStatus.APPROVED.value and successes >= min_successes:
                path = proposal.target.get("path")
                if path == "direction_min_confidence":
                    target_value = float(proposal.target.get("to", current_threshold))
                    target_value = max(0.0, min(1.0, target_value))
                    if target_value != current_threshold:
                        revert_handle = {"path": path, "previous": current_threshold}
                        get_config_port().set(direction_min_confidence=target_value)
                        current_threshold = target_value
                        proposal.mark_applied(revert_handle)
                        applied_any = True
                        successes = 0
                    else:
                        proposal.status = LearnStatus.SCORED.value
                else:
                    proposal.status = LearnStatus.SCORED.value

            proposal.metadata.setdefault("gate", {})
            proposal.metadata["gate"].update(
                {
                    "successes": successes,
                    "min_successes": min_successes,
                    "min_confidence": min_conf,
                }
            )
            gate_updates[gate_key] = {
                "successes": successes,
                "min_successes": min_successes,
                "min_confidence": min_conf,
                "updated_at": now(),
            }
            proposal_dicts.append(proposal.to_dict())

        policy_snapshot = None  # release reference
    else:
        proposal_dicts = []

    learn_id = f"{policy_id}:{episode_id}" if policy_id else f"episode:{episode_id}"
    payload = build_learn_payload(
        policy_id=policy_id,
        metrics=metrics,
        reasons=reasons,
        latencies=latencies,
        counts=counts,
        proposals=proposals,
        applied=applied_any,
        scope="policy",
        ttl=None,
        proposal_id=learn_id,
        approval=(
            "auto-applied"
            if any(p.status == LearnStatus.APPLIED.value for p in proposals)
            else "approved"
            if any(p.status == LearnStatus.APPROVED.value for p in proposals)
            else "pending"
        ),
    )

    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "learn",
            "payload": payload,
            "evidence_ids": [],
        },
    )

    if proposal_dicts:
        persist_episode_learning(run_dir, payload)
        learn_home.mkdir(parents=True, exist_ok=True)
        update_policy_snapshot(learn_home, policy_id, proposal_dicts, gate_updates=gate_updates)

    return {
        "payload": payload,
        "proposal_count": len(proposals),
        "applied_count": sum(1 for p in proposals if p.accepted),
        "kinds": summarise_learn_kinds(proposal_dicts),
    }
