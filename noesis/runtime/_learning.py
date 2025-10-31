from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import _config as _cfg
from ..learn import (
    LearnMode,
    LearnProposal,
    LearnStatus,
    build_learn_payload,
    derive_target_key,
    load_policy_snapshot,
    persist_episode_learning,
    summarise_learn_kinds,
    update_policy_snapshot,
)
from ..trace.events import write_event
from ._utils import now
from ._events import last_event_of_phase

__all__ = ["maybe_emit_learn_event"]


def maybe_emit_learn_event(
    *,
    run_dir: Path,
    episode_id: str,
    events: List[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    cfg_snapshot = _cfg.get()
    mode = LearnMode(cfg_snapshot.get("learn_mode", LearnMode.RECORD.value))
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
    current_threshold = float(cfg_snapshot.get("direction_min_confidence", 0.5))
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

    if proposals:
        default_home = Path.home() / ".noesis" / "state"
        learn_home = Path(cfg_snapshot.get("learn_home", str(default_home))).expanduser()
        learn_home.mkdir(parents=True, exist_ok=True)
        policy_snapshot = load_policy_snapshot(learn_home, policy_id)

        min_conf = float(cfg_snapshot.get("learn_auto_apply_min_confidence", 0.75))
        min_successes = int(cfg_snapshot.get("learn_auto_apply_min_successes", 3))

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
                        _cfg.set(direction_min_confidence=target_value)
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
        default_home = Path.home() / ".noesis" / "state"
        learn_home = Path(cfg_snapshot.get("learn_home", str(default_home))).expanduser()
        learn_home.mkdir(parents=True, exist_ok=True)
        update_policy_snapshot(learn_home, policy_id, proposal_dicts, gate_updates=gate_updates)

    return {
        "payload": payload,
        "proposal_count": len(proposals),
        "applied_count": sum(1 for p in proposals if p.accepted),
        "kinds": summarise_learn_kinds(proposal_dicts),
    }
