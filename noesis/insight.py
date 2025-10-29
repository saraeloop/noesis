"""
Insight hooks for Noēsis.

Lightweight analysis utilities that compute roll-up metrics from
episode summaries and event streams.
"""

from __future__ import annotations
from typing import Any, Dict, List, DefaultDict
from collections import defaultdict

__all__ = ["compute_metrics"]

def compute_metrics(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute high-level insight metrics from a summary + event stream.

    Assumptions:
      - Direction events carry payload.reason in:
          {"applied","empty_patch","policy_low_confidence","not_dict_input","veto"}
      - Vetoes end the run; summaries may mark status="blocked" (not required here).
      - Optional timestamps: event.get("ts") in milliseconds (int) or ISO8601 (ignored if absent).
    """
    total_events = len(events)

    # Filter and normalize safely
    dir_events = [e for e in events if e.get("phase") == "direction" and isinstance(e.get("payload"), dict)]
    reasons: DefaultDict[str, int] = defaultdict(int)
    applied = 0
    vetoed = 0

    for e in dir_events:
        reason = (e["payload"].get("reason") or "").lower()
        reasons[reason] += 1
        if reason == "applied":
            applied += 1
        elif reason == "veto":
            vetoed += 1

    dir_count = len(dir_events)
    applied_rate = (applied / dir_count) if dir_count else 0.0
    veto_rate = (vetoed / dir_count) if dir_count else 0.0

    # Pull existing metrics if present, default sanely
    m = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    steps = total_events
    ideal_steps = int(m.get("ideal_steps", 0))

    # Optional: latency if you later add timestamps
    time_to_veto_ms = None  # reserved for future use

    return {
        # carry over any existing task-level scores (zeros are fine placeholders)
        "success": int(m.get("success", 0)),
        "steps": steps,
        "ideal_steps": ideal_steps,
        "action_efficiency": float(m.get("action_efficiency", 0.0)),
        "tool_correctness": float(m.get("tool_correctness", 0.0)),
        "coherence": float(m.get("coherence", 0.0)),
        "intuition_alignment": float(m.get("intuition_alignment", 0.0)),

        # direction insights
        "direction_events": dir_count,
        "direction_applied": applied,
        "direction_vetoed": vetoed,
        "direction_applied_rate": applied_rate,
        "direction_veto_rate": veto_rate,
        "direction_top_reasons": sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)[:3],

        # future-friendly fields
        "time_to_veto_ms": time_to_veto_ms,
    }