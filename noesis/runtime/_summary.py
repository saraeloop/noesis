from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List
import hashlib
import json

from ..state.episode import EpisodeSummary
from ..trace.events import read_events, write_event
from ..trace.summary import write_summary
from ..insight import compute_metrics
from ..intuition import Intuition, IntuitionMode
from ._utils import compute_duration, format_diff_item, now
from ._learning import maybe_emit_learn_event
from ..interfaces.config import ConfigSnapshot

__all__ = ["finalize_summary"]


def _agents_config_hash(using_label: Optional[str], intuition: Optional[Intuition], intuition_enabled: bool) -> str:
    descriptor: Dict[str, Any] = {
        "using": using_label or "core",
        "intuition": None,
    }
    if intuition_enabled and intuition:
        descriptor["intuition"] = {
            "class": intuition.__class__.__name__,
            "version": getattr(intuition, "__version__", getattr(intuition, "version", None)),
            "mode": getattr(getattr(intuition, "mode", None), "value", None),
        }
    payload = json.dumps(descriptor, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def finalize_summary(
    *,
    run_dir: Path,
    episode_id: str,
    task: str,
    seed: int,
    started_at: str,
    intuition_enabled: bool,
    intuition_mode: IntuitionMode,
    using_label: Optional[str],
    tags: Optional[Dict[str, Any]],
    intuition: Optional[Intuition],
    schema_version: str,
    config: ConfigSnapshot,
    ports: Dict[str, str],
) -> None:
    snapshot = config
    events = read_events(run_dir)
    duration_sec = compute_duration(events)

    flags: Dict[str, Any] = {
        "intuition": intuition_enabled,
        "mode": intuition_mode.value if intuition_enabled else "off",
    }
    if using_label is not None:
        flags["using"] = using_label

    summary = EpisodeSummary(
        schema_version=schema_version,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        duration_sec=duration_sec,
        flags=flags,
        agents_config_hash=_agents_config_hash(using_label, intuition, intuition_enabled),
        answer={},
        metrics=compute_metrics({}, events),
        tags=tags or {},
        ports=ports,
    ).__dict__

    metrics_bucket = summary.setdefault("metrics", {})
    metrics_bucket["intuition_events"] = sum(1 for e in events if e.get("phase") == "intuition")

    learn_info = maybe_emit_learn_event(
        run_dir=run_dir,
        episode_id=episode_id,
        events=events,
        metrics=metrics_bucket,
        config=snapshot,
    )
    if learn_info:
        metrics_bucket["learn_proposals"] = learn_info["proposal_count"]
        metrics_bucket["learn_applied"] = learn_info["applied_count"]
        if learn_info["kinds"]:
            experimental = metrics_bucket.setdefault("experimental", {})
            experimental["learn_kinds"] = learn_info["kinds"]

    direction_events = [e for e in events if e.get("phase") == "direction"]
    metrics_bucket["direction_events"] = len(direction_events)
    metrics_bucket["direction_applied"] = sum(
        1
        for e in direction_events
        if e.get("payload", {}).get("applied") and e.get("payload", {}).get("status") != "blocked"
    )
    metrics_bucket["direction_vetoed"] = sum(
        1 for e in direction_events if e.get("payload", {}).get("status") == "blocked"
    )

    last_payload = direction_events[-1].get("payload", {}) if direction_events else {}
    diff_strings: List[str] = []
    for diff_item in (last_payload.get("diff") or []):
        try:
            diff_strings.append(format_diff_item(diff_item))
        except Exception:
            continue

    write_event(
        run_dir,
        {
            "timestamp": now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "insight",
            "payload": summary.get("metrics", {}),
            "evidence_ids": [],
        },
    )

    direction_flags = {
        "applied": metrics_bucket["direction_applied"],
        "vetoed": metrics_bucket["direction_vetoed"],
        "last_diff": diff_strings,
        "threshold": snapshot.direction_min_confidence,
    }
    policy_tag = last_payload.get("policy")
    if policy_tag:
        direction_flags["policy"] = policy_tag
    summary.setdefault("flags", {})["direction"] = direction_flags

    write_summary(run_dir, summary)
