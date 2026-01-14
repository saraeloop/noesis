"""
Runtime summary finalisation helpers.

Public facade replacing the legacy `_summary` module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List
import hashlib

from noesis.state.episode import EpisodeSummary
from noesis.trace.events import read_events, write_event, canonical_dumps
from noesis.trace.summary import write_summary
from noesis.domain.faculties import validate_hook_sequence
from noesis.intuition import Intuition, IntuitionMode
from noesis.interfaces.config import ConfigSnapshot

from .learning import maybe_emit_learn_event
from .normalization import compute_summary_metrics_from_events, normalize_using
from .utils import compute_duration, format_diff_item, now, parse_iso8601

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
    payload = canonical_dumps(descriptor, default=str).encode("utf-8")
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
    process_id: str | None = None,
    process_name: str | None = None,
    process_kind: str | None = None,
    process_run_index: int | None = None,
    schema_version: str,
    config: ConfigSnapshot,
    ports: Dict[str, str],
    adapter_result: str,
    outcome: str,
    verification: Dict[str, object | None],
) -> None:
    snapshot = config
    events = read_events(run_dir)
    validate_hook_sequence([event.get("phase", "") for event in events if isinstance(event.get("phase"), str)])
    duration_sec = compute_duration(events)

    flags: Dict[str, Any] = {
        "intuition": intuition_enabled,
        "mode": intuition_mode.value if intuition_enabled else "off",
    }
    # Governance configuration flags (best effort; remain strings for schema stability)
    governance_mode = getattr(config, "governance_mode", "off")
    if hasattr(governance_mode, "value"):
        governance_mode = governance_mode.value
    flags["governance_mode"] = str(governance_mode)
    failure_policy = getattr(config, "governance_failure_policy", None)
    if hasattr(failure_policy, "value"):
        failure_policy = failure_policy.value
    if failure_policy is not None:
        flags["governance_failure_policy"] = str(failure_policy)
    using_norm = normalize_using(using_label)
    if using_norm is not None:
        flags["using"] = using_norm.display

    summary_metrics, insight_metrics = compute_summary_metrics_from_events(events)

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
        metrics=summary_metrics,
        tags=tags or {},
        ports=ports,
    ).__dict__

    summary["adapter_result"] = adapter_result
    summary["outcome"] = outcome
    summary["verification"] = verification
    if process_id and process_name:
        summary["process"] = {
            "id": process_id,
            "name": process_name,
            "run_index": process_run_index,
            "kind": process_kind,
        }

    metrics_bucket = summary.setdefault("metrics", {})
    summary.setdefault("insight", {})["metrics"] = insight_metrics.to_mapping()
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
    policy_tag: Optional[str] = None
    for direction_event in reversed(direction_events):
        payload = direction_event.get("payload", {}) or {}
        status = payload.get("status")
        if payload.get("policy") and status not in {"skipped"}:
            policy_tag = payload.get("policy")
            last_payload = payload
            break
    diff_strings: List[str] = []
    for diff_item in (last_payload.get("diff") or []):
        try:
            diff_strings.append(format_diff_item(diff_item))
        except Exception:
            continue

    insight_payload: dict[str, object] = {
        "summary_path": "summary.json",
        "metrics": {
            "plan_adherence": metrics_bucket.get("plan_adherence"),
            "tool_coverage": metrics_bucket.get("tool_coverage"),
            "veto_count": metrics_bucket.get("veto_count"),
            "success": metrics_bucket.get("success"),
            "act_count": metrics_bucket.get("act_count"),
        },
    }
    insight_timestamp = now()
    latest_ts = _latest_event_timestamp(events)
    if latest_ts:
        latest_dt = parse_iso8601(latest_ts)
        current_dt = parse_iso8601(insight_timestamp)
        if latest_dt and current_dt and current_dt < latest_dt:
            insight_timestamp = latest_ts
    write_event(
        run_dir,
        {
            "timestamp": insight_timestamp,
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "insight",
            "payload": insight_payload,
            "evidence_ids": [],
        },
    )

    direction_flags = {
        "applied": metrics_bucket["direction_applied"],
        "vetoed": metrics_bucket["direction_vetoed"],
        "last_diff": diff_strings,
        "threshold": snapshot.direction_min_confidence,
    }
    if policy_tag:
        direction_flags["policy"] = policy_tag
    summary.setdefault("flags", {})["direction"] = direction_flags

    manifest_meta = summary.setdefault("manifest", {})
    manifest_meta.setdefault("path", "manifest.json")

    write_summary(run_dir, summary)


def _latest_event_timestamp(events: List[Dict[str, Any]]) -> Optional[str]:
    latest_dt = None
    latest_ts = None
    for event in events:
        ts = event.get("timestamp")
        if not isinstance(ts, str):
            continue
        parsed = parse_iso8601(ts)
        if parsed is None:
            continue
        if latest_dt is None or parsed > latest_dt:
            latest_dt = parsed
            latest_ts = ts
    return latest_ts
