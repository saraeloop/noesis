from __future__ import annotations

import json
from typing import Dict, Iterable, Any

from ..formatters import format_rows_for_plain


class PlainRenderer:
    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet

    def banner(self, text: str) -> None:
        if not self.quiet:
            print(text)

    def echo(self, text: str) -> None:
        if not self.quiet:
            print(text)

    def print_list(self, rows: Iterable[Dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    print(eid)
            return
        for line in format_rows_for_plain(rows):
            print(line)

    def print_summary(self, summary: Dict[str, Any]) -> None:
        if self.quiet:
            eid = summary.get("episode_id", "")
            print(eid)
            return

        flags = summary.get("flags", {})
        direction_flags = flags.get("direction", {})
        metrics = summary.get("metrics", {})

        print("Episode")
        print(f"  id      : {summary.get('episode_id')}")
        print(f"  task    : {summary.get('task')}")
        print(f"  started : {summary.get('started_at')}")
        print(f"  duration: {summary.get('duration_sec')}s")

        print("\nFlags")
        print(f"  intuition : {flags.get('intuition')} (mode={flags.get('mode')})")
        if "using" in flags:
            print(f"  using     : {flags['using']}")

        print("\nDirection")
        policy = direction_flags.get("policy", "—")
        diff = ", ".join(direction_flags.get("last_diff", []) or []) or "—"
        print(f"  policy    : {policy}")
        print(f"  threshold : {direction_flags.get('threshold')}")
        print(f"  applied   : {direction_flags.get('applied')}  vetoed: {direction_flags.get('vetoed')}")
        print(f"  last_diff : {diff}")

        print("\nMetrics (highlights)")
        for key in (
            "direction_events",
            "direction_applied",
            "direction_vetoed",
            "veto_rate",
            "top_reasons",
            "steps",
        ):
            print(f"  {key:18}: {metrics.get(key)}")

    def print_events(self, events: Iterable[Dict[str, Any]]) -> None:
        for event in events:
            timestamp = event.get("timestamp", "")
            phase = event.get("phase", "")
            payload = event.get("payload", {}) or {}
            detail_parts = []
            for key in ("reason", "status"):
                val = payload.get(key)
                if val is not None:
                    detail_parts.append(f"{key}={val}")
            diff = payload.get("diff")
            if diff:
                detail_parts.append(f"diff={diff}")
            line = f"[{timestamp}] {phase:<10} {'  '.join(detail_parts)}".rstrip()
            print(line)

    def json(self, data: Any) -> None:
        print(json.dumps(data, indent=2, ensure_ascii=False))
