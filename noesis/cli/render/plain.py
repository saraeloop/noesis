from __future__ import annotations

import json
from typing import Dict, Iterable, Any, List

from ..view_models import EpisodeDashboardVM, TimelineRowVM

from ..formatters import format_ps_rows_for_plain, format_rows_for_plain, format_duration, truncate

_TIMELINE_COLS = {
    "dt": 8,
    "phase": 12,
    "agent": 16,
    "status": 10,
    "summary": 50,
}

_KPI_COLS = {
    "label": 16,
    "value": 16,
}

_PHASE_COLS = {
    "phase": 12,
    "duration": 10,
}


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

    def print_ps(self, rows: Iterable[Dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    print(eid)
            return
        for line in format_ps_rows_for_plain(rows):
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

    def _filter_timeline(self, rows: Iterable[TimelineRowVM], grep: str | None) -> List[TimelineRowVM]:
        if not grep:
            return list(rows)
        terms = [term.strip().lower() for term in grep.split() if term.strip()]
        filtered: List[TimelineRow] = []
        for row in rows:
            haystack = f"phase={row.phase} agent={row.agent} summary={row.summary}".lower()
            if all(term in haystack for term in terms):
                filtered.append(row)
        return filtered

    def print_viewer(self, view: EpisodeDashboardVM, *, grep: str | None = None) -> None:
        header = view.header
        print(f"Episode {header.episode_id} [{header.status_label}]")
        print(f"  started_at: {header.started_at}")
        print(f"  duration  : {format_duration(header.duration)}")
        print("  chips     : " + "  ".join(
            item for item in (
                _chip("using", view.chips.using),
                _chip("planner", view.chips.planner_mode),
                _chip("duration", view.chips.duration_str),
                _chip("schema", view.chips.schema_str),
            ) if item
        ))

        kpis = view.kpis
        print("\nKPIs")
        kpi_rows = [
            ["success%", _format_percent_value(kpis.success_pct)],
            ["plan_adherence", _format_ratio(kpis.plan_adherence)],
            ["veto_count", str(kpis.veto_count) if kpis.veto_count is not None else "—"],
            ["tool_coverage", _format_ratio(kpis.tool_coverage)],
            ["first_action", kpis.first_action or "—"],
        ]
        for line in _render_table(
            headers=["KPI", "VALUE"],
            rows=kpi_rows,
            widths=[_KPI_COLS["label"], _KPI_COLS["value"]],
            align_right={1},
        ):
            print(line)

        if view.phase_breakdown:
            print("\nPhase Breakdown")
            phase_rows = [[item.phase, f"{item.ms} ms"] for item in view.phase_breakdown]
            for line in _render_table(
                headers=["PHASE", "DURATION"],
                rows=phase_rows,
                widths=[_PHASE_COLS["phase"], _PHASE_COLS["duration"]],
                align_right={1},
            ):
                print(line)

        rows = self._filter_timeline(view.timeline_rows, grep)
        print("\nTimeline")
        if not rows:
            timeline_rows = [["-", "-", "-", "-", "no events matched"]]
        else:
            timeline_rows = [
                [
                    row.dt_str,
                    row.phase,
                    row.agent,
                    row.status or "—",
                    row.summary or "",
                ]
                for row in rows
            ]
        for line in _render_table(
            headers=["Δt", "phase", "agent", "status", "summary"],
            rows=timeline_rows,
            widths=[
                _TIMELINE_COLS["dt"],
                _TIMELINE_COLS["phase"],
                _TIMELINE_COLS["agent"],
                _TIMELINE_COLS["status"],
                _TIMELINE_COLS["summary"],
            ],
            align_right={0},
        ):
            print(line)

        if view.suggestions:
            print("\nNext")
            for suggestion in view.suggestions:
                print(f"  {suggestion}")


def _chip(label: str, value: str | None) -> str:
    if not value:
        return ""
    return f"{label}={value}"


def _format_percent_value(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def _render_table(
    *,
    headers: List[str],
    rows: List[List[str]],
    widths: List[int],
    align_right: set[int] | None = None,
) -> List[str]:
    align_right = align_right or set()

    def _format_cell(value: str, width: int, *, right: bool) -> str:
        text = truncate(str(value), max_width=width)
        return text.rjust(width) if right else text.ljust(width)

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    header_cells = []
    for idx, (header, width) in enumerate(zip(headers, widths)):
        header_cells.append(f" {_format_cell(header, width, right=idx in align_right)} ")
    header_line = "|" + "|".join(header_cells) + "|"

    lines = [border, header_line, border]
    for row in rows:
        row_cells = []
        for idx, (value, width) in enumerate(zip(row, widths)):
            row_cells.append(f" {_format_cell(value, width, right=idx in align_right)} ")
        lines.append("|" + "|".join(row_cells) + "|")
    lines.append(border)
    return lines
