"""
Runtime utility helpers.

Public facade replacing the legacy `_utils` module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import json

__all__ = [
    "now",
    "parse_iso8601",
    "compute_duration",
    "format_diff_item",
    "fmt_value",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso8601(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_duration(events: List[Dict[str, Any]]) -> float:
    start_at: datetime | None = None
    end_at: datetime | None = None
    for evt in events:
        ts = evt.get("timestamp")
        if not isinstance(ts, str):
            continue
        parsed = parse_iso8601(ts)
        if parsed is None:
            continue
        if start_at is None and evt.get("phase") == "start":
            start_at = parsed
        if evt.get("phase") in {"terminate", "error"}:
            end_at = parsed
    if start_at and end_at and end_at >= start_at:
        return (end_at - start_at).total_seconds()
    return 0.0


def fmt_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return repr(val)
    return json.dumps(val)


def format_diff_item(item: Dict[str, Any]) -> str:
    before = fmt_value(item.get("before"))
    after = fmt_value(item.get("after"))
    return f"{item.get('key')}: {before}→{after}"
