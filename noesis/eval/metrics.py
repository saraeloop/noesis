"""
Evaluation metrics (pure functions over dicts).

Return a 'metrics' dict with fields:
    success, steps, ideal_steps, action_efficiency,
    tool_correctness, coherence, intuition_alignment
Implementation can evolve; keep keys stable.
"""
from __future__ import annotations
from typing import Dict, List, Any

def compute_metrics(summary: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Placeholder: return a metrics dict with default values; replace later."""
    direction_events = [e for e in events if e.get("phase") == "direction"]
    direction_applied = sum(
        1
        for e in direction_events
        if e.get("payload", {}).get("applied") and e.get("payload", {}).get("status") != "blocked"
    )
    direction_vetoed = sum(1 for e in direction_events if e.get("payload", {}).get("status") == "blocked")
    return {
        "success": 0,
        "steps": len(events),
        "ideal_steps": summary.get("metrics", {}).get("ideal_steps", 0),
        "action_efficiency": 0.0,
        "tool_correctness": 0.0,
        "coherence": 0.0,
        "intuition_alignment": 0.0,
        "direction_events": len(direction_events),
        "direction_applied": direction_applied,
        "direction_vetoed": direction_vetoed,
    }
