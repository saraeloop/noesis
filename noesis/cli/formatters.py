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
    header = f"{'LAST_SEEN':>20}  {'PROCESS':24}  {'STATUS':10}  {'KIND':10}  OUTCOME"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        last_seen = truncate((row.get("last_seen_at", "") or "")[:20], max_width=20)
        process = truncate((row.get("process_name") or row.get("process_id") or "")[:24], max_width=24)
        status = truncate((row.get("status") or "")[:10], max_width=10)
        kind = truncate((row.get("kind") or "")[:10], max_width=10)
        outcome = row.get("last_run_outcome") or ""
        lines.append(f"{last_seen:>20}  {process:24}  {status:10}  {kind:10}  {outcome}")
    return lines
