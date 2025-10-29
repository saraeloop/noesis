from __future__ import annotations

from typing import Dict, Iterable, List


def truncate(s: str, *, max_width: int) -> str:
    if len(s) <= max_width:
        return s
    return s[: max_width - 1] + "…"


def format_rows_for_plain(rows: Iterable[Dict[str, str]]) -> List[str]:
    lines: List[str] = []
    header = f"{'STARTED_AT':>25}  {'EPISODE_ID':28}  TASK"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        started = truncate(row.get("started_at", "")[:25], max_width=25)
        episode = truncate(row.get("episode_id", "")[:28], max_width=28)
        task = row.get("task", "")
        lines.append(f"{started:>25}  {episode:28}  {task}")
    return lines
