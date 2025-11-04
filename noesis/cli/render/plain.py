from __future__ import annotations

import json
from typing import Dict, Iterable, Any, List

from ..viewer import EpisodeView, TimelineRow, ValidationIssue

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

    def _filter_timeline(self, rows: Iterable[TimelineRow], grep: str | None) -> List[TimelineRow]:
        if not grep:
            return list(rows)
        terms = [term.strip().lower() for term in grep.split() if term.strip()]
        filtered: List[TimelineRow] = []
        for row in rows:
            haystack = f"phase={row.phase} agent={row.agent} note={row.note}".lower()
            if all(term in haystack for term in terms):
                filtered.append(row)
        return filtered

    def _print_validation(self, issues: Iterable[ValidationIssue]) -> None:
        issues = list(issues)
        if not issues:
            return
        print("\nValidation")
        for issue in issues:
            print(f"  ! {issue.format()}")

    def print_viewer(self, view: EpisodeView, *, grep: str | None = None) -> None:
        header = view.header
        print("Episode")
        print(f"  id          : {header.get('episode_id')}")
        print(f"  started_at  : {header.get('started_at')}")
        print(f"  planner_mode: {header.get('planner_mode')}")
        intuition = "on" if header.get("intuition_enabled") else "off"
        print(f"  intuition   : {intuition}")
        if header.get("using"):
            print(f"  using       : {header.get('using')}")
        policies = header.get("policies") or []
        if policies:
            print(f"  policies    : {', '.join(policies)}")

        kpis = view.kpis
        print("\nKPIs")
        print(f"  success        : {kpis.get('success')}")
        print(f"  plan_adherence : {kpis.get('plan_adherence')}")
        print(f"  veto_count     : {kpis.get('veto_count')}")
        print(f"  tool_coverage  : {kpis.get('tool_coverage')}")
        phase_ms = kpis.get("phase_ms") or {}
        if phase_ms:
            print("  phase_ms:")
            for phase, value in phase_ms.items():
                print(f"    - {phase}: {value} ms")

        if view.governance:
            gov = view.governance
            print("\nGovernance")
            print(f"  decision       : {gov.get('decision')}")
            print(f"  rule_id        : {gov.get('rule_id')}")
            if gov.get("policy_id"):
                print(f"  policy         : {gov.get('policy_id')}@{gov.get('policy_version')}")
            if gov.get("message"):
                print(f"  message        : {gov.get('message')}")
            if gov.get("time_to_veto_ms") is not None:
                print(f"  time_to_veto_ms: {gov.get('time_to_veto_ms')}")

        rows = self._filter_timeline(view.timeline, grep)
        print("\nTimeline")
        if not rows:
            print("  (no events matched)")
        else:
            for row in rows:
                delta = row.delta_label()
                note = row.note or ""
                print(f"  [{row.timestamp}] {delta:>9} {row.phase:<10} {row.agent:<20} {note}")

        self._print_validation(view.validation)
