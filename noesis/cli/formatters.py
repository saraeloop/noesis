from __future__ import annotations

from typing import Dict, Iterable, List


def truncate(s: str, *, max_width: int) -> str:
    if len(s) <= max_width:
        return s
    return s[: max_width - 1] + "…"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    remainder = seconds - (minutes * 60)
    if minutes < 60:
        return f"{minutes}m {remainder:.1f}s"
    hours = int(minutes // 60)
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


def format_rows_for_plain(rows: Iterable[Dict[str, str]]) -> List[str]:
    lines: List[str] = []
    header = f"{'STARTED_AT':>25}  {'EPISODE_ID':28}  TASK"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        started = truncate(row.get("started_at", "")[:25], max_width=25)
        episode = truncate(row.get("episode_id", "")[:28], max_width=28)
        task = row.get("task", "")
        manifest_status = row.get("manifest_status")
        note = ""
        if manifest_status and manifest_status not in {"ok", None}:
            note = f"  [manifest:{manifest_status}]"
        lines.append(f"{started:>25}  {episode:28}  {task}{note}")
    return lines


def format_ps_rows_for_plain(rows: Iterable[Dict[str, str]]) -> List[str]:
    lines: List[str] = []
    header = f"{'STARTED_AT':>20}  {'EPISODE':10}  {'STATUS':16}  {'USING':12}  DURATION"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        started = truncate((row.get("started_at", "") or "")[:20], max_width=20)
        episode = truncate((row.get("episode_short") or row.get("episode_id") or "")[:10], max_width=10)
        status = truncate(row.get("status", "")[:16], max_width=16)
        using = truncate(row.get("using", "")[:12], max_width=12)
        duration = row.get("duration", "")
        lines.append(f"{started:>20}  {episode:10}  {status:16}  {using:12}  {duration}")
    return lines
