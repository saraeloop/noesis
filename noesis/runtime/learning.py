from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config as _cfg
from ..learn import (
    LearnMode,
    build_learn_payload,
    persist_episode_learning,
    summarise_learn_kinds,
    update_policy_snapshot,
)
from ..trace.events import write_event
from .utils import now
from .events import last_event_of_phase

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

    reflect_event = last_event_of_phase(events, "reflect") or {}
    reasons = reflect_event.get("payload", {}).get("reasons", []) or []

    latencies = metrics.get("latencies", {}) or {}
    counts = {
        "plan": metrics.get("plan_count", 0),
        "act": metrics.get("steps", 0),
        "reflect": metrics.get("reflect_count", 0),
    }

    proposals: List[Dict[str, Any]] = []
    direction_vetoed = metrics.get("direction_vetoed", 0)
    current_threshold = float(cfg_snapshot.get("direction_min_confidence", 0.5))
    if direction_vetoed:
        proposed_threshold = min(1.0, round(current_threshold + 0.05, 2))
        if proposed_threshold > current_threshold:
            proposals.append(
                {
                    "kind": "threshold_tune",
                    "path": "direction_min_confidence",
                    "from": current_threshold,
                    "to": proposed_threshold,
                    "reason": "veto_detected_in_episode",
                    "accepted": False,
                }
            )

    applied_any = False
    if mode is LearnMode.APPLY:
        for proposal in proposals:
            path = proposal.get("path")
            if path == "direction_min_confidence":
                target = float(proposal.get("to", current_threshold))
                target = max(0.0, min(1.0, target))
                if target != current_threshold:
                    _cfg.set(direction_min_confidence=target)
                    proposal["accepted"] = True
                    applied_any = True
                else:
                    proposal["accepted"] = False
            else:
                proposal["accepted"] = False
    else:
        for proposal in proposals:
            proposal.setdefault("accepted", False)

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
        approval="pending",
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

    if proposals:
        persist_episode_learning(run_dir, payload)
    if proposals and applied_any:
        default_home = Path.home() / ".noesis" / "state"
        learn_home = Path(cfg_snapshot.get("learn_home", str(default_home))).expanduser()
        learn_home.mkdir(parents=True, exist_ok=True)
        update_policy_snapshot(learn_home, policy_id, proposals, applied=applied_any)

    return {
        "payload": payload,
        "proposal_count": len(proposals),
        "applied_count": sum(1 for p in proposals if p.get("accepted")),
        "kinds": summarise_learn_kinds(proposals),
    }
