from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from .. import formatters
from ..view_models import EpisodeDashboardVM, TimelineRowVM

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


class RichRenderer:
    def __init__(self, console: Console, *, quiet: bool = False) -> None:
        self.console = console
        self.quiet = quiet

    def banner(self, text: str) -> None:
        if not self.quiet:
            self.console.print(Text(text, style="title"))

    def echo(self, text: str) -> None:
        if not self.quiet:
            self.console.print(text)

    def print_list(self, rows: Iterable[Dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    self.console.print(eid)
            return

        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=None,
            expand=True,
            pad_edge=False,
            row_styles=None,
        )
        table.add_column("STARTED_AT", style="muted", no_wrap=True, justify="right", max_width=25)
        table.add_column("EPISODE_ID", style="bright_cyan", no_wrap=True, max_width=28)
        table.add_column("TASK", style=_safe_style(self.console, "val", "white"))
        for row in rows:
            table.add_row(
                (row.get("started_at", "")[:25]),
                (row.get("episode_id", "")[:28]),
                row.get("task", ""),
            )
        self.console.print(table)

    def print_ps(self, rows: Iterable[Dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    self.console.print(eid)
            return

        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=None,
            expand=True,
            pad_edge=False,
        )
        table.add_column("STARTED_AT", style="muted", no_wrap=True, max_width=20)
        table.add_column("EPISODE", style="bright_cyan", no_wrap=True, max_width=12)
        table.add_column("STATUS", style=_safe_style(self.console, "val", "white"), no_wrap=True, max_width=8)
        table.add_column("USING", style="muted", no_wrap=True, max_width=14)
        table.add_column("DURATION", style=_safe_style(self.console, "val", "white"), no_wrap=True, max_width=10)
        for row in rows:
            status = row.get("status", "")
            style = _status_style(status)
            table.add_row(
                row.get("started_at", "")[:20],
                (row.get("episode_short") or row.get("episode_id") or "")[:10],
                Text(status, style=style),
                row.get("using", ""),
                row.get("duration", ""),
            )
        self.console.print(table)

    def print_summary(self, summary: Dict[str, Any]) -> None:
        if self.quiet:
            self.console.print(summary.get("episode_id", ""))
            return

        flags = summary.get("flags", {}) or {}
        direction_flags = flags.get("direction", {}) or {}
        metrics = summary.get("metrics", {}) or {}

        header = Text(f"Episode {summary.get('episode_id','')}", style="title")

        body = Table.grid(padding=(0, 1))
        body.add_row(Text("task", style="key"), Text(summary.get("task", ""), style="val"))
        body.add_row(Text("started", style="key"), Text(summary.get("started_at", ""), style="val"))
        dur_val = summary.get("duration_sec")
        body.add_row(Text("duration", style="key"), Text(f"{dur_val}s", style="val"))

        flags_tbl = Table.grid(padding=(0, 1))
        flags_tbl.add_row(Text("intuition", style="key"), Text(f"{flags.get('intuition')} (mode={flags.get('mode')})", style="val"))
        if "using" in flags:
            flags_tbl.add_row(Text("using", style="key"), Text(str(flags["using"]), style="val"))

        dir_tbl = Table.grid(padding=(0, 1))
        dir_tbl.add_row(Text("policy", style="key"), Text(direction_flags.get("policy", "—"), style="val"))
        dir_tbl.add_row(Text("threshold", style="key"), Text(str(direction_flags.get("threshold")), style="val"))
        dir_tbl.add_row(Text("applied", style="key"), Text(str(direction_flags.get("applied")), style="ok"))
        dir_tbl.add_row(Text("vetoed", style="key"), Text(str(direction_flags.get("vetoed")), style="err"))
        diff_text = ", ".join(direction_flags.get("last_diff", []) or []) or "—"
        dir_tbl.add_row(Text("last_diff", style="key"), Text(diff_text, style="val"))

        metrics_tbl = Table.grid(padding=(0, 1))
        for key in (
            "direction_events",
            "direction_applied",
            "direction_vetoed",
            "veto_rate",
            "top_reasons",
            "steps",
        ):
            metrics_tbl.add_row(Text(key, style="key"), Text(str(metrics.get(key)), style="val"))

        self.console.print(Panel(body, title=header, border_style="title"))
        self.console.print(Panel(flags_tbl, title="[title]Flags[/]"))
        self.console.print(Panel(dir_tbl, title="[title]Direction[/]"))
        self.console.print(Panel(metrics_tbl, title="[title]Metrics[/]"))

    def print_events(self, events: Iterable[Dict[str, Any]]) -> None:
        for event in events:
            phase = event.get("phase", "")
            style = f"phase.{phase}" if f"phase.{phase}" in self.console.theme.styles else "val"
            timestamp = Text(event.get("timestamp", ""), style="muted")
            payload = event.get("payload", {}) or {}
            extras = []
            for key in ("reason", "status"):
                if key in payload:
                    extras.append(f"{key}={payload[key]}")
            diff = payload.get("diff")
            if diff:
                extras.append(f"diff={diff}")
            line = Text.assemble(
                "[",
                timestamp,
                "] ",
                Text(f"{phase:<10}", style=style),
                " ",
                Text("  ".join(extras), style="val"),
            )
            self.console.print(line)

    def json(self, data: Any) -> None:
        src = json.dumps(data, indent=2, ensure_ascii=False)
        self.console.print(Syntax(src, "json", word_wrap=True))

    def _filter_timeline(self, rows: Iterable[TimelineRowVM], grep: str | None) -> list[TimelineRowVM]:
        if not grep:
            return list(rows)
        terms = [term.strip().lower() for term in grep.split() if term.strip()]
        filtered: list[TimelineRow] = []
        for row in rows:
            haystack = f"phase={row.phase} agent={row.agent} summary={row.summary}".lower()
            if all(term in haystack for term in terms):
                filtered.append(row)
        return filtered

    def render_episode_dashboard(self, vm: EpisodeDashboardVM, *, grep: str | None = None, debug: bool = False) -> None:
        header = vm.header
        chips = vm.chips

        title = Text(f"Episode {header.episode_id}", style="title")
        badge = Text(f" {header.status_label} ", style=_status_style(header.status_label))
        header_grid = Table.grid(expand=True)
        header_grid.add_column(ratio=1)
        header_grid.add_column(justify="right", no_wrap=True)
        header_grid.add_row(title, badge)

        chip_text = Text("  ".join(_format_chip(label, value) for label, value in (
            ("using", chips.using),
            ("planner", chips.planner_mode),
            ("duration", chips.duration_str),
            ("schema", chips.schema_str),
        ) if value))
        header_body = Table.grid()
        header_body.add_row(header_grid)
        if chip_text.plain:
            header_body.add_row(Text(chip_text.plain, style="muted"))
        self.console.print(Panel(header_body, border_style="title"))

        kpis = vm.kpis
        kpi_table = Table(
            title="[title]KPIs[/]",
            box=box.SQUARE,
            show_header=True,
            header_style="title",
            expand=True,
        )
        kpi_table.add_column("KPI", style=_safe_style(self.console, "key", "cyan"), no_wrap=True, width=_KPI_COLS["label"])
        kpi_table.add_column("VALUE", style=_safe_style(self.console, "val", "white"), justify="right", width=_KPI_COLS["value"])
        kpi_table.add_row("success%", _format_percent_value(kpis.success_pct))
        kpi_table.add_row("plan_adherence", _format_ratio(kpis.plan_adherence))
        kpi_table.add_row("veto_count", str(kpis.veto_count) if kpis.veto_count is not None else "—")
        kpi_table.add_row("tool_coverage", _format_ratio(kpis.tool_coverage))
        kpi_table.add_row("first_action", kpis.first_action or "—")

        phase_panel = None
        if vm.phase_breakdown:
            phase_table = Table(
                title="[title]Phase Breakdown[/]",
                show_header=True,
                header_style="title",
                box=box.SQUARE,
                expand=True,
            )
            phase_table.add_column("PHASE", style=_safe_style(self.console, "val", "white"), no_wrap=True, width=_PHASE_COLS["phase"])
            phase_table.add_column("DURATION", style="muted", justify="right", no_wrap=True, width=_PHASE_COLS["duration"])
            for item in vm.phase_breakdown:
                phase_style = _phase_style(self.console, item.phase)
                phase_table.add_row(Text(item.phase, style=phase_style), f"{item.ms} ms")
            phase_panel = phase_table

        if phase_panel and self.console.size.width >= 100:
            from rich.columns import Columns

            self.console.print(Columns([kpi_table, phase_panel], expand=True))
        else:
            self.console.print(kpi_table)
            if phase_panel:
                self.console.print(phase_panel)

        rows = self._filter_timeline(vm.timeline_rows, grep)
        timeline_table = Table(
            title="[title]Timeline[/]",
            show_header=True,
            header_style="title",
            box=box.SQUARE,
            expand=True,
        )
        timeline_table.add_column("Δt", style="muted", no_wrap=True, justify="right", width=_TIMELINE_COLS["dt"])
        timeline_table.add_column("PHASE", style=_safe_style(self.console, "val", "white"), no_wrap=True, width=_TIMELINE_COLS["phase"])
        timeline_table.add_column("AGENT", style="muted", no_wrap=True, width=_TIMELINE_COLS["agent"])
        timeline_table.add_column("STATUS", style=_safe_style(self.console, "val", "white"), no_wrap=True, width=_TIMELINE_COLS["status"])
        timeline_table.add_column("SUMMARY", style=_safe_style(self.console, "val", "white"), no_wrap=True, width=_TIMELINE_COLS["summary"])

        if not rows:
            timeline_table.add_row("-", "-", "-", "-", "no events matched")
        else:
            for row in rows:
                phase_style = _phase_style(self.console, row.phase)
                timeline_table.add_row(
                    formatters.truncate(row.dt_str, max_width=_TIMELINE_COLS["dt"]),
                    Text(formatters.truncate(row.phase, max_width=_TIMELINE_COLS["phase"]), style=phase_style),
                    Text(formatters.truncate(row.agent, max_width=_TIMELINE_COLS["agent"]), style="muted"),
                    Text(
                        formatters.truncate(row.status or "—", max_width=_TIMELINE_COLS["status"]),
                        style=_status_style(row.status),
                    ),
                    Text(formatters.truncate(row.summary or "", max_width=_TIMELINE_COLS["summary"]), style="val"),
                )
        self.console.print(timeline_table)

        if vm.suggestions:
            suggestions = "\n".join(f"[muted]$[/] {item}" for item in vm.suggestions)
            self.console.print(Panel(suggestions, title="[title]Next[/]"))

    def print_viewer(self, view: EpisodeDashboardVM, *, grep: str | None = None) -> None:
        self.render_episode_dashboard(view, grep=grep)


def _status_style(label: str) -> str:
    normalized = label.lower()
    if normalized in {"success", "ok"}:
        return "ok"
    if normalized == "audit":
        return "warn"
    if normalized in {"vetoed", "error"}:
        return "err"
    return "muted"


def _format_chip(label: str, value: str | None) -> str:
    return f"{label}:{value}" if value else ""


def _format_percent_value(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def _safe_style(console: Console, style_name: str, fallback: str = "white") -> str:
    """Get a style name if it exists in the theme, otherwise return fallback."""
    try:
        console.get_style(style_name)
        return style_name
    except Exception:  # noqa: BLE001 - rich raises errors for missing styles
        return fallback


def _phase_style(console: Console, phase: str) -> str:
    style_name = f"phase.{phase}"
    try:
        console.get_style(style_name)
    except Exception:  # noqa: BLE001 - rich raises errors for missing styles
        return "val"
    return style_name
