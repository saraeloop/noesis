from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from .. import formatters
from ..view_models import EpisodeDashboardVM, TimelineRowVM


# ---------------------------------------------------------------------------
# Responsive Breakpoints (inspired by CSS media queries)
# ---------------------------------------------------------------------------

class Breakpoint(Enum):
    """Terminal width breakpoints for adaptive layouts."""
    COMPACT = "compact"    # < 60 cols  (mobile-like, single column)
    STANDARD = "standard"  # 60-99 cols (typical split terminal)
    WIDE = "wide"          # >= 100 cols (full-width terminal)


# Breakpoint thresholds
_COMPACT_MAX = 60
_STANDARD_MAX = 100


def detect_breakpoint(console: Console) -> Breakpoint:
    """Detect the current breakpoint based on console width."""
    width = console.size.width
    if width < _COMPACT_MAX:
        return Breakpoint.COMPACT
    if width < _STANDARD_MAX:
        return Breakpoint.STANDARD
    return Breakpoint.WIDE


# ---------------------------------------------------------------------------
# Adaptive Column Configurations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnConfig:
    """Configuration for a table column at a specific breakpoint."""
    name: str
    width: int | None
    visible: bool = True
    no_wrap: bool = True
    justify: str = "left"


# Timeline columns per breakpoint
_TIMELINE_CONFIGS: dict[Breakpoint, list[ColumnConfig]] = {
    Breakpoint.COMPACT: [
        ColumnConfig("Δt", width=7, justify="right"),
        ColumnConfig("PHASE", width=8),
        ColumnConfig("SUMMARY", width=None),  # flex
    ],
    Breakpoint.STANDARD: [
        ColumnConfig("Δt", width=8, justify="right"),
        ColumnConfig("PHASE", width=10),
        ColumnConfig("STATUS", width=8),
        ColumnConfig("SUMMARY", width=None),  # flex
    ],
    Breakpoint.WIDE: [
        ColumnConfig("Δt", width=8, justify="right"),
        ColumnConfig("PHASE", width=12),
        ColumnConfig("AGENT", width=16),
        ColumnConfig("STATUS", width=10),
        ColumnConfig("SUMMARY", width=50),
    ],
}

# KPI columns per breakpoint
_KPI_CONFIGS: dict[Breakpoint, list[ColumnConfig]] = {
    Breakpoint.COMPACT: [
        ColumnConfig("KPI", width=12),
        ColumnConfig("VALUE", width=10, justify="right"),
    ],
    Breakpoint.STANDARD: [
        ColumnConfig("KPI", width=14),
        ColumnConfig("VALUE", width=14, justify="right"),
    ],
    Breakpoint.WIDE: [
        ColumnConfig("KPI", width=16),
        ColumnConfig("VALUE", width=16, justify="right"),
    ],
}

# Phase breakdown columns per breakpoint
_PHASE_CONFIGS: dict[Breakpoint, list[ColumnConfig]] = {
    Breakpoint.COMPACT: [
        ColumnConfig("PHASE", width=8),
        ColumnConfig("MS", width=6, justify="right"),
    ],
    Breakpoint.STANDARD: [
        ColumnConfig("PHASE", width=10),
        ColumnConfig("DURATION", width=8, justify="right"),
    ],
    Breakpoint.WIDE: [
        ColumnConfig("PHASE", width=12),
        ColumnConfig("DURATION", width=10, justify="right"),
    ],
}


# Legacy fixed widths (kept for backward compatibility)
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
        table.add_column("STARTED_AT", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, justify="right", max_width=25)
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
        table.add_column("STARTED_AT", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, max_width=20)
        table.add_column("EPISODE", style="bright_cyan", no_wrap=True, max_width=12)
        table.add_column("STATUS", style=_safe_style(self.console, "val", "white"), no_wrap=True, max_width=8)
        table.add_column("USING", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, max_width=14)
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
        filtered: list[TimelineRowVM] = []
        for row in rows:
            haystack = f"phase={row.phase} agent={row.agent} summary={row.summary}".lower()
            if all(term in haystack for term in terms):
                filtered.append(row)
        return filtered

    def render_episode_dashboard(self, vm: EpisodeDashboardVM, *, grep: str | None = None, debug: bool = False) -> None:
        """Render the episode dashboard with adaptive layout based on terminal width."""
        bp = detect_breakpoint(self.console)
        
        self._render_header(vm)
        self._render_kpis_and_phases(vm, bp)
        self._render_timeline(vm, grep, bp)
        self._render_suggestions(vm, bp)

    def _render_header(self, vm: EpisodeDashboardVM) -> None:
        """Render the episode header panel."""
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

    def _render_kpis_and_phases(self, vm: EpisodeDashboardVM, bp: Breakpoint) -> None:
        """Render KPIs and phase breakdown with adaptive layout."""
        kpi_config = _KPI_CONFIGS[bp]
        phase_config = _PHASE_CONFIGS[bp]
        kpis = vm.kpis

        kpi_table = Table(
            title="[title]KPIs[/]",
            box=box.SQUARE,
            show_header=True,
            header_style="title",
            expand=True,
        )
        for col in kpi_config:
            kpi_table.add_column(
                col.name,
                style=_safe_style(self.console, "key" if col.name == "KPI" else "val", "cyan" if col.name == "KPI" else "white"),
                no_wrap=col.no_wrap,
                width=col.width,
                justify=col.justify,
            )

        # Adaptive KPI labels
        kpi_labels = {
            Breakpoint.COMPACT: ["success", "adherence", "veto", "coverage", "1st act"],
            Breakpoint.STANDARD: ["success%", "plan_adhere", "veto_count", "tool_cov", "first_act"],
            Breakpoint.WIDE: ["success%", "plan_adherence", "veto_count", "tool_coverage", "first_action"],
        }
        labels = kpi_labels[bp]
        kpi_table.add_row(labels[0], _format_percent_value(kpis.success_pct))
        kpi_table.add_row(labels[1], _format_ratio(kpis.plan_adherence))
        kpi_table.add_row(labels[2], str(kpis.veto_count) if kpis.veto_count is not None else "—")
        kpi_table.add_row(labels[3], _format_ratio(kpis.tool_coverage))
        kpi_table.add_row(labels[4], kpis.first_action or "—")

        phase_panel = None
        if vm.phase_breakdown:
            phase_table = Table(
                title="[title]Phases[/]" if bp == Breakpoint.COMPACT else "[title]Phase Breakdown[/]",
                show_header=True,
                header_style="title",
                box=box.SQUARE,
                expand=True,
            )
            for col in phase_config:
                phase_table.add_column(
                    col.name,
                    style=_safe_style(self.console, "val", "white"),
                    no_wrap=col.no_wrap,
                    width=col.width,
                    justify=col.justify,
                )
            for item in vm.phase_breakdown:
                phase_style = _phase_style(self.console, item.phase)
                duration_str = f"{item.ms}ms" if bp == Breakpoint.COMPACT else f"{item.ms} ms"
                phase_table.add_row(Text(item.phase, style=phase_style), duration_str)
            phase_panel = phase_table

        # Side-by-side layout only on WIDE breakpoint
        if phase_panel and bp == Breakpoint.WIDE:
            from rich.columns import Columns
            self.console.print(Columns([kpi_table, phase_panel], expand=True))
        else:
            self.console.print(kpi_table)
            if phase_panel:
                self.console.print(phase_panel)

    def _render_timeline(self, vm: EpisodeDashboardVM, grep: str | None, bp: Breakpoint) -> None:
        """Render the timeline table with adaptive columns."""
        timeline_config = _TIMELINE_CONFIGS[bp]
        rows = self._filter_timeline(vm.timeline_rows, grep)

        timeline_table = Table(
            title="[title]Timeline[/]",
            show_header=True,
            header_style="title",
            box=box.SQUARE,
            expand=True,
        )

        # Add columns based on breakpoint config
        for col in timeline_config:
            style = _safe_style(self.console, "muted", "dim") if col.name in ("Δt", "AGENT") else _safe_style(self.console, "val", "white")
            timeline_table.add_column(
                col.name,
                style=style,
                no_wrap=col.no_wrap,
                width=col.width,
                justify=col.justify,
            )

        if not rows:
            empty_row = ["-"] * len(timeline_config)
            empty_row[-1] = "no events matched"
            timeline_table.add_row(*empty_row)
        else:
            for row in rows:
                phase_style = _phase_style(self.console, row.phase)
                row_data = self._build_timeline_row(row, bp, phase_style)
                timeline_table.add_row(*row_data)

        self.console.print(timeline_table)

    def _build_timeline_row(self, row: TimelineRowVM, bp: Breakpoint, phase_style: str) -> list[Text | str]:
        """Build a timeline row based on breakpoint."""
        if bp == Breakpoint.COMPACT:
            return [
                formatters.truncate(row.dt_str, max_width=7),
                Text(formatters.truncate(row.phase, max_width=8), style=phase_style),
                Text(formatters.truncate(row.summary or "", max_width=40), style="val"),
            ]
        elif bp == Breakpoint.STANDARD:
            return [
                formatters.truncate(row.dt_str, max_width=8),
                Text(formatters.truncate(row.phase, max_width=10), style=phase_style),
                Text(formatters.truncate(row.status or "—", max_width=8), style=_status_style(row.status)),
                Text(formatters.truncate(row.summary or "", max_width=50), style="val"),
            ]
        else:  # WIDE
            return [
                formatters.truncate(row.dt_str, max_width=8),
                Text(formatters.truncate(row.phase, max_width=12), style=phase_style),
                Text(formatters.truncate(row.agent, max_width=16), style="muted"),
                Text(formatters.truncate(row.status or "—", max_width=10), style=_status_style(row.status)),
                Text(formatters.truncate(row.summary or "", max_width=50), style="val"),
            ]

    def _render_suggestions(self, vm: EpisodeDashboardVM, bp: Breakpoint) -> None:
        """Render the suggestions panel."""
        if not vm.suggestions:
            return
        
        # On compact, show fewer suggestions
        suggestions_to_show = vm.suggestions[:2] if bp == Breakpoint.COMPACT else vm.suggestions
        suggestions = "\n".join(f"[muted]$[/] {item}" for item in suggestions_to_show)
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
