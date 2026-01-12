from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from .. import formatters
from ..view_models import EpisodeDashboardVM, TimelineRowVM, build_verification_section
from ..help_content import HelpScreen, HomeScreen
from ..theme import build_theme_tokens, Breakpoint, detect_breakpoint as _detect_breakpoint, get_box_style, outcome_badge, normalize_outcome


def detect_breakpoint(console: Console) -> Breakpoint:
    """Detect the current breakpoint based on console width."""
    return _detect_breakpoint(console.size.width)


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
        self._theme = build_theme_tokens()

    def banner(self, text: str) -> None:
        if not self.quiet:
            self.console.print(Text(text, style="title"))

    def echo(self, text: str) -> None:
        if not self.quiet:
            self.console.print(text)

    def print_list(self, rows: list[dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    self.console.print(eid)
            return

        table = Table(
            show_header=True,
            header_style="header",
            box=None,
            expand=True,
            pad_edge=False,
            row_styles=None,
        )
        table.add_column("STARTED_AT", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, justify="right", max_width=25)
        table.add_column("EPISODE_ID", style=_safe_style(self.console, "accent", "bright_cyan"), no_wrap=True, max_width=28)
        table.add_column("TASK", style=_safe_style(self.console, "val", "white"))
        for row in rows:
            table.add_row(
                (row.get("started_at", "")[:25]),
                (row.get("episode_id", "")[:28]),
                row.get("task", ""),
            )
        self.console.print(table)

    def print_ps(self, rows: list[dict[str, str]], *, quiet: bool = False) -> None:
        if quiet or self.quiet:
            for row in rows:
                eid = row.get("episode_id")
                if eid:
                    self.console.print(eid)
            return

        table = Table(
            show_header=True,
            header_style="header",
            box=None,
            expand=True,
            pad_edge=False,
        )
        table.add_column("STARTED_AT", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, max_width=20)
        table.add_column("EPISODE", style=_safe_style(self.console, "accent", "bright_cyan"), no_wrap=True, max_width=12)
        table.add_column("STATUS", style=_safe_style(self.console, "val", "white"), no_wrap=True, max_width=16)
        table.add_column("USING", style=_safe_style(self.console, "muted", "dim"), no_wrap=True, max_width=14)
        table.add_column("DURATION", style=_safe_style(self.console, "val", "white"), no_wrap=True, max_width=10)
        for row in rows:
            status = row.get("status", "")
            outcome = normalize_outcome(
                row.get("outcome"),
                status=row.get("status_raw"),
                success=row.get("success"),
            )
            badge = outcome_badge(outcome)
            style = _safe_style(self.console, badge.style, "white")
            status_text = Text(badge.label, style=style)
            table.add_row(
                row.get("started_at", "")[:20],
                (row.get("episode_short") or row.get("episode_id") or "")[:10],
                status_text,
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

        border_style = _safe_style(self.console, "panel", "dim")
        self.console.print(Panel(body, title=header, border_style=border_style))
        self.console.print(Panel(flags_tbl, title="[title]Flags[/]", border_style=border_style))
        self.console.print(Panel(dir_tbl, title="[title]Direction[/]", border_style=border_style))
        self.console.print(Panel(metrics_tbl, title="[title]Metrics[/]", border_style=border_style))

    def print_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            phase = event.get("phase", "")
            style = _phase_style(self.console, phase)
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

    def print_execution_map(self, execution_map, *, compact: bool = False) -> None:
        if self.quiet:
            return
        phases = execution_map.phases()
        if not compact:
            table = Table(
                show_header=True,
                header_style="title",
                box=box.SQUARE,
                expand=True,
            )
            for phase in phases:
                table.add_column(
                    phase.phase,
                    justify="center",
                    style=_safe_style(self.console, "key", "cyan"),
                    no_wrap=True,
                )
            row = [Text(phase.status, style=_execution_status_style(phase.status)) for phase in phases]
            table.add_row(*row)
            self.console.print(table)
            return
        line = Text()
        for idx, phase in enumerate(phases):
            if idx:
                line.append(" | ", style="muted")
            line.append(f"{phase.phase}: ", style="muted")
            line.append(phase.status, style=_execution_status_style(phase.status))
        self.console.print(line)

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
        self._render_execution_map(vm)
        self._render_verification(vm)
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

        # Governance summary line (if present)
        gov = header.governance
        if gov:
            gov_line = Text()
            gov_line.append("governance: ", style="muted")
            gov_line.append(gov.decision, style=_status_style(gov.decision))
            if gov.rule_id:
                gov_line.append(f" {gov.rule_id}", style="err" if gov.decision == "VETO" else "val")
            if gov.score is not None:
                gov_line.append(f" score={gov.score:.2f}", style="warn")
            gov_line.append(f" enforced={str(gov.enforced).lower()}", style="muted")
            header_body.add_row(gov_line)

        border_style = _safe_style(self.console, "panel", "dim")
        self.console.print(Panel(header_body, border_style=border_style))

    def _render_execution_map(self, vm: EpisodeDashboardVM) -> None:
        execution_map = vm.execution_map
        table = Table(
            title="[title]Execution Map[/]",
            show_header=True,
            header_style="title",
            box=box.SQUARE,
            expand=True,
        )
        for phase in execution_map.phases():
            table.add_column(
                phase.phase,
                justify="center",
                style=_safe_style(self.console, "key", "cyan"),
                no_wrap=True,
            )
        row = [
            Text(phase.status, style=_execution_status_style(phase.status))
            for phase in execution_map.phases()
        ]
        table.add_row(*row)
        self.console.print(table)

    def _render_verification(self, vm: EpisodeDashboardVM) -> None:
        verification = vm.verification
        table = Table(
            title="[title]Verification[/]",
            show_header=False,
            box=box.SQUARE,
            expand=True,
        )
        table.add_column("key", style=_safe_style(self.console, "key", "cyan"), no_wrap=True)
        table.add_column("value", style=_safe_style(self.console, "val", "white"))

        adapter_result = verification.adapter_result or "—"
        table.add_row("adapter_result", Text(adapter_result, style=_execution_status_style(adapter_result)))
        outcome = verification.outcome.status or "—"
        if verification.outcome.summary:
            outcome = f"{outcome} ({verification.outcome.summary})"
        table.add_row("outcome", Text(outcome, style=_execution_status_style(verification.outcome.status or "")))
        passed = "null" if verification.passed is None else str(verification.passed).lower()
        if verification.passed is None:
            passed_style = "muted"
        elif verification.passed:
            passed_style = _execution_status_style("passed")
        else:
            passed_style = _execution_status_style("failed")
        table.add_row("passed", Text(passed, style=passed_style))
        if verification.error:
            table.add_row("error", Text(verification.error, style="err"))

        diff = verification.workspace_diff
        if diff is None:
            table.add_row("workspace_diff", "—")
            table.add_row("changed_files", "—")
        else:
            table.add_row(
                "workspace_diff",
                f"added={len(diff.added)} modified={len(diff.modified)} deleted={len(diff.deleted)}",
            )
            changed = _format_changed_files(diff, limit=10) or "—"
            table.add_row("changed_files", changed)

        failure = _first_failed_assertion(verification) or "—"
        table.add_row("first_failure", failure)
        self.console.print(table)

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
        border_style = _safe_style(self.console, "panel", "dim")
        self.console.print(Panel(suggestions, title="[title]Next[/]", border_style=border_style))

    def print_viewer(self, view: EpisodeDashboardVM, *, grep: str | None = None) -> None:
        self.render_episode_dashboard(view, grep=grep)

    def print_run_summary(self, episode_id: str, task: str, summary: Dict[str, Any]) -> None:
        if self.quiet:
            self.console.print(episode_id)
            return
        header = Table.grid(padding=(0, 1))
        header.add_row(Text(f"Episode {episode_id}", style="title"))
        header.add_row(Text(f"Task: {task}", style="val"))
        self.console.print(Panel(header, border_style=_safe_style(self.console, "panel", "dim")))

        verification = build_verification_section(summary)
        agent_line = _format_agent_result(summary.get("adapter_result"))
        verify_line = _format_verify_result(verification)
        outcome = outcome_badge(summary.get("outcome"))
        outcome_line = Text(outcome.label, style=_safe_style(self.console, outcome.style, "val"))

        body = Table.grid(padding=(0, 2))
        body.add_row(Text("Agent", style="key"), agent_line)
        body.add_row(Text("Verify", style="key"), verify_line)
        body.add_row(Text("Outcome", style="key"), outcome_line)
        if verification.workspace_diff is not None:
            body.add_row(Text("Changed", style="key"), _format_diff_counts(verification.workspace_diff))
        self.console.print(body)

        failure = _first_failed_assertion(verification)
        if failure:
            self.console.print(Text(f"First failure: {failure}", style="err"))

        self.console.print(Text(f"-> noesis view {episode_id}      full details", style="muted"))

    def print_view_compact(self, view: EpisodeDashboardVM) -> None:
        header = Table.grid(padding=(0, 1))
        header.add_row(Text(f"Episode {view.header.episode_id}", style="title"))
        if view.header.task:
            header.add_row(Text(f"Task: {view.header.task}", style="val"))
        if view.header.duration is not None:
            header.add_row(Text(f"Duration: {formatters.format_duration(view.header.duration)}", style="muted"))
        outcome = outcome_badge(view.verification.outcome.status)
        self.console.print(Panel(header, title=outcome.label, border_style=_safe_style(self.console, "panel", "dim")))

        summary_table = Table(title="[title]Summary[/]", box=box.SQUARE, show_header=False, expand=True)
        summary_table.add_column("key", style=_safe_style(self.console, "key", "cyan"), no_wrap=True)
        summary_table.add_column("value", style=_safe_style(self.console, "val", "white"))
        summary_table.add_row("Agent", _format_agent_result(view.verification.adapter_result))
        summary_table.add_row("Verify", _format_verify_result(view.verification))
        summary_table.add_row("Outcome", Text(outcome.label, style=_safe_style(self.console, outcome.style, "val")))
        self.console.print(summary_table)

        self._render_execution_map(view)
        self._render_changed_files(view)
        self._render_assertions(view)

    def print_view_verbose(self, view: EpisodeDashboardVM) -> None:
        bp = detect_breakpoint(self.console)
        self._render_kpis_and_phases(view, bp)
        self._render_timeline(view, None, bp)

    def _render_changed_files(self, view: EpisodeDashboardVM) -> None:
        diff = view.verification.workspace_diff
        if diff is None:
            return
        table = Table(
            title="[title]Changed Files[/]",
            show_header=True,
            header_style="title",
            box=box.SQUARE,
            expand=True,
        )
        table.add_column("CHANGE", style=_safe_style(self.console, "val", "white"))
        table.add_column("STATUS", style=_safe_style(self.console, "muted", "dim"))

        category = _change_category(view.verification)
        label, style = _change_label(category)
        rows = _flatten_changes(diff, limit=10)
        if not rows:
            table.add_row("—", label)
            self.console.print(table)
            return
        for change in rows:
            table.add_row(change, Text(label, style=style))
        self.console.print(table)

    def _render_assertions(self, view: EpisodeDashboardVM) -> None:
        assertions = view.verification.assertions
        if not assertions:
            return
        table = Table(
            title="[title]Assertions[/]",
            show_header=True,
            header_style="title",
            box=box.SQUARE,
            expand=True,
        )
        table.add_column("RESULT", style=_safe_style(self.console, "val", "white"), no_wrap=True)
        table.add_column("ASSERTION", style=_safe_style(self.console, "val", "white"))
        for assertion in assertions:
            result = "PASS" if assertion.passed else "FAIL"
            result_style = "ok" if assertion.passed else "err"
            detail = _format_assertion_detail(assertion)
            table.add_row(Text(result, style=_safe_style(self.console, result_style, "white")), detail)
        self.console.print(table)

    def print_home(self, screen: HomeScreen) -> None:
        """Render the compact home screen."""
        if self.quiet:
            return
        from ..theme import NAV_ARROW

        header = Text()
        header.append("Noēsis", style="brand")
        header.append(" ", style="muted")
        header.append(screen.version, style="version")
        self.console.print(header)
        self.console.print(Text(screen.tagline, style="tagline"))
        self.console.print()

        if screen.next_actions:
            self.console.print(Text("Commands", style="title"))
            for action in screen.next_actions[:3]:
                action_line = Text()
                action_line.append(f"  {NAV_ARROW}  ", style="nav.arrow")
                action_line.append(action.command, style="nav.command")
                padding = max(1, 36 - len(action.command))
                action_line.append(" " * padding, style="muted")
                action_line.append(action.description, style="nav.desc")
                self.console.print(action_line)
            self.console.print()

    def print_home_details(self, screen: HomeScreen) -> None:
        """Render the detailed home dashboard sections."""
        if self.quiet:
            return
        from ..theme import section_line

        width = min(self.console.width or 80, 80)

        cfg = screen.config
        config_line = Text()
        config_line.append("governance ", style="home.config.key")
        config_line.append(cfg.governance_mode, style="home.config.val")
        config_line.append("   planner ", style="home.config.key")
        config_line.append(cfg.planner_mode, style="home.config.val")
        config_line.append("   intuition ", style="home.config.key")
        config_line.append(cfg.intuition_mode, style="home.config.val")
        config_line.append("   runs ", style="home.config.key")
        config_line.append(cfg.runs_dir, style="home.config.val")
        self.console.print(config_line)
        self.console.print()

        if screen.last_episode:
            self.console.print(Text(section_line("last", width), style="separator"))
            self.console.print()

            last = screen.last_episode
            outcome = normalize_outcome(last.outcome, status=last.status, success=last.success)
            badge = outcome_badge(outcome)
            status_style = _safe_style(self.console, badge.style, "val")

            status_line = Text()
            status_line.append("  ", style="muted")
            status_line.append(badge.label, style=status_style)
            status_line.append("   ", style="muted")
            status_line.append(formatters.truncate(last.episode_id, max_width=14), style="accent")
            status_line.append("   ", style="muted")
            status_line.append(last.duration, style="muted")
            self.console.print(status_line)

            task_line = Text()
            task_line.append("    ", style="muted")
            task_line.append(formatters.truncate(last.task, max_width=65), style="val")
            self.console.print(task_line)

            if last.status == "VETOED" and last.rule_id:
                self.console.print()
                rule_line = Text()
                rule_line.append("    rule   ", style="muted")
                rule_line.append(last.rule_id, style="err")
                if last.score is not None:
                    rule_line.append(f"  score={last.score:.2f}", style="warn")
                self.console.print(rule_line)

                if last.message:
                    why_line = Text()
                    why_line.append("    why    ", style="muted")
                    why_line.append(formatters.truncate(last.message, max_width=55), style="muted")
                    self.console.print(why_line)

            self.console.print()

        if screen.recent_episodes:
            self.console.print(Text(section_line("recent", width), style="separator"))
            self.console.print()
            for ep in screen.recent_episodes[:5]:
                outcome = normalize_outcome(ep.outcome, status=ep.status, success=ep.success)
                badge = outcome_badge(outcome)
                status_style = _safe_style(self.console, badge.style, "muted")
                ep_line = Text()
                ep_line.append(f"  {ep.time_str}  ", style="muted")
                ep_line.append(f"{badge.label:<16}", style=status_style)
                ep_line.append(f"  {ep.episode_short}  ", style="accent")
                ep_line.append(formatters.truncate(ep.task, max_width=40), style="muted")
                self.console.print(ep_line)
            self.console.print()

    def print_help(self, screen: HelpScreen) -> None:
        """Render help screen in Rich mode."""
        if self.quiet:
            return

        box_style = get_box_style() or box.ROUNDED
        border = _safe_style(self.console, "border", "grey42")

        # Header
        header_grid = Table.grid(padding=(0, 1))
        header_grid.add_row(
            Text(f"Noēsis CLI {screen.version}", style="title"),
        )
        header_grid.add_row(Text(screen.tagline, style="accent"))
        header_grid.add_row(Text(f"Usage: {screen.usage}", style="muted"))
        self.console.print(Panel(header_grid, box=box_style, border_style=border))

        # Command groups
        for group in screen.groups:
            table = Table.grid(padding=(0, 1))
            for cmd in group.commands:
                table.add_row(Text(cmd.name, style="accent"), Text(cmd.one_liner, style="val"))
            self.console.print(Panel(table, title=f"[group.title]{group.title}[/]", box=box_style, border_style=border))

        # Examples
        examples = "\n".join(f"[muted]$[/] {example}" for example in screen.examples)
        self.console.print(Panel(examples, title="[group.title]Examples[/]", box=box_style, border_style=border))

        # Footer
        self.console.print(Text(screen.footer, style="hint"))

    def print_command_help(self, text: str, *, title: str | None = None) -> None:
        if self.quiet:
            return
        layout = self._theme.layout
        body = Syntax(text.rstrip(), "text", word_wrap=True)
        border_style = _safe_style(self.console, "panel", "dim")
        self.console.print(
            Panel(
                body,
                title=f"[title]{title}[/]" if title else None,
                border_style=border_style,
                padding=layout.panel_padding,
                width=layout.panel_width,
            )
        )

    def print_explain(self, vm: Any) -> None:
        """Render explain output in Rich mode - modern bubbletea style."""
        if self.quiet:
            return
        from ..theme import section_line, status_symbol, NAV_ARROW, BULLET

        width = min(self.console.width or 80, 80)

        # Episode header section
        self.console.print(Text(section_line(vm.episode_id, width), style="separator"))
        self.console.print()

        # Status with symbol (large, prominent)
        status_upper = vm.status.upper()
        status_style = f"status.{status_upper.lower()}"
        sym = status_symbol(status_upper, ascii_mode=True)
        status_line = Text()
        status_line.append(f"  {sym} ", style=_safe_style(self.console, status_style, "val"))
        status_line.append(status_upper, style=_safe_style(self.console, status_style, "val"))
        if vm.governance and vm.governance.enforced:
            status_line.append("   enforced", style="warn")
        self.console.print(status_line)
        self.console.print()

        # Task
        task_line = Text()
        task_line.append("  Task: ", style="muted")
        task_line.append(formatters.truncate(vm.task, max_width=65), style="val")
        self.console.print(task_line)
        self.console.print()

        # Governance Decision section
        if vm.governance:
            gov = vm.governance
            self.console.print(Text(section_line("governance", width), style="separator"))
            self.console.print()

            decision_style = f"status.{gov.decision.lower()}"
            dec_line = Text()
            dec_line.append("  decision   ", style="muted")
            dec_line.append(gov.decision.upper(), style=_safe_style(self.console, decision_style, "val"))
            if gov.enforced:
                dec_line.append(" (enforced)", style="warn")
            self.console.print(dec_line)

            mode_line = Text()
            mode_line.append("  mode       ", style="muted")
            mode_line.append(gov.mode, style="val")
            self.console.print(mode_line)

            if gov.rule_id:
                rule_line = Text()
                rule_line.append("  rule       ", style="muted")
                rule_line.append(gov.rule_id, style="err")
                self.console.print(rule_line)

            if gov.policy_id:
                pol_line = Text()
                pol_line.append("  policy     ", style="muted")
                pol_line.append(gov.policy_id, style="val")
                if gov.policy_version:
                    pol_line.append(f" v{gov.policy_version}", style="muted")
                self.console.print(pol_line)

            if gov.score is not None:
                score_line = Text()
                score_line.append("  score      ", style="muted")
                score_line.append(f"{gov.score:.2f}", style="warn")
                self.console.print(score_line)

            if gov.message:
                msg_line = Text()
                msg_line.append("  message    ", style="muted")
                msg_line.append(gov.message, style="val")
                self.console.print(msg_line)

            self.console.print()

        # Evidence section
        if vm.intuition_advice or vm.direction_blocks or vm.risky_tokens:
            self.console.print(Text(section_line("evidence", width), style="separator"))
            self.console.print()

            if vm.intuition_advice:
                self.console.print(Text("  Intuition Advice", style="title"))
                for advice in vm.intuition_advice:
                    adv_line = Text()
                    adv_line.append(f"    {BULLET}  ", style="nav.bullet")
                    adv_line.append(advice.advice, style="val")
                    if advice.confidence is not None:
                        adv_line.append(f" (confidence={advice.confidence:.2f})", style="muted")
                    self.console.print(adv_line)
                self.console.print()

            if vm.direction_blocks:
                self.console.print(Text("  Direction Blocks", style="title"))
                for block in vm.direction_blocks:
                    block_line = Text()
                    block_line.append(f"    {BULLET}  ", style="nav.bullet")
                    block_line.append(block.status, style="err")
                    block_line.append(": ", style="muted")
                    block_line.append(block.reason, style="val")
                    self.console.print(block_line)
                    if block.rule_id:
                        rule_line = Text()
                        rule_line.append("       rule: ", style="muted")
                        rule_line.append(block.rule_id, style="err")
                        self.console.print(rule_line)
                self.console.print()

            if vm.risky_tokens:
                self.console.print(Text("  Risky Tokens", style="title"))
                tokens_line = Text()
                tokens_line.append(f"    {BULLET}  ", style="nav.bullet")
                tokens_line.append(", ".join(vm.risky_tokens), style="warn")
                self.console.print(tokens_line)
                self.console.print()

        # Causal Chain section
        if vm.causal_chain:
            self.console.print(Text(section_line("causal chain", width), style="separator"))
            self.console.print()
            parts = []
            for step in vm.causal_chain:
                if step.status:
                    parts.append(f"{step.phase}({step.status})")
                else:
                    parts.append(step.phase)
            chain_line = Text()
            chain_line.append("  ", style="muted")
            chain_line.append(" -> ".join(parts), style="muted")
            self.console.print(chain_line)
            self.console.print()

        # Next Actions section
        if vm.next_actions:
            self.console.print(Text(section_line("next", width), style="separator"))
            self.console.print()
            for action in vm.next_actions:
                action_line = Text()
                action_line.append(f"  {NAV_ARROW}  ", style="nav.arrow")
                action_line.append(action, style="nav.command")
                self.console.print(action_line)
            self.console.print()

        # Closing separator
        self.console.print(Text("─" * width, style="separator"))


def _status_style(label: str) -> str:
    """Map episode status or governance decision to a display style.

    Handles both episode statuses (vetoed, error, ok, success, audit) and
    governance decisions (VETO, AUDIT, ALLOW).
    """
    normalized = label.lower()
    if normalized in {"success", "ok", "allow"}:
        return "ok"
    if normalized == "audit":
        return "warn"
    if normalized in {"vetoed", "error", "veto"}:
        return "err"
    return "muted"


def _execution_status_style(label: str) -> str:
    normalized = str(label).lower()
    if normalized in {"ok", "passed", "success"}:
        return "ok"
    if normalized in {"skipped", "unverified", "success_unverified"}:
        return "warn"
    if normalized in {"failed", "error", "vetoed", "goal_not_achieved"}:
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


def _format_changed_files(diff, *, limit: int) -> str:
    entries: list[str] = []
    entries.extend([f"+{path}" for path in sorted(diff.added)])
    entries.extend([f"~{path}" for path in sorted(diff.modified)])
    entries.extend([f"-{path}" for path in sorted(diff.deleted)])
    return ", ".join(entries[:limit])


def _first_failed_assertion(verification) -> str | None:
    for assertion in verification.assertions:
        if assertion.passed:
            continue
        target = _format_assertion_target(assertion.target)
        reason = f": {assertion.reason}" if assertion.reason else ""
        if target:
            return f"{assertion.name} {target}{reason}"
        return f"{assertion.name}{reason}"
    return None


def _format_assertion_target(target) -> str | None:
    if isinstance(target, tuple):
        return "[" + ", ".join(target) + "]"
    if isinstance(target, str):
        return target
    return None


def _format_agent_result(adapter_result: object) -> Text:
    if adapter_result == "success":
        return Text("OK", style="ok")
    if adapter_result == "error":
        return Text("FAIL", style="err")
    if adapter_result == "skipped":
        return Text("SKIPPED", style="warn")
    return Text("UNKNOWN", style="muted")


def _format_verify_result(verification) -> Text:
    assertions = verification.assertions
    total = len(assertions)
    passed = sum(1 for assertion in assertions if assertion.passed)
    if verification.passed is True:
        label = f"PASSED ({passed} of {total})" if total else "PASSED"
        return Text(label, style="ok")
    if verification.passed is False:
        label = f"FAILED ({passed} of {total})" if total else "FAILED"
        return Text(label, style="err")
    if verification.error:
        return Text(f"ERROR ({verification.error})", style="err")
    if verification.provided is False:
        return Text("SKIPPED", style="warn")
    return Text("UNVERIFIED", style="warn")


def _format_diff_counts(diff) -> Text:
    if diff is None:
        return Text("—", style="muted")
    return Text(
        f"+ {len(diff.added)} added   ~ {len(diff.modified)} modified   - {len(diff.deleted)} deleted",
        style="val",
    )


def _change_category(verification) -> str:
    if verification.passed is True:
        return "expected"
    if verification.passed is False:
        return "violation"
    return "unexpected"


def _change_label(category: str) -> tuple[str, str]:
    if category == "expected":
        return ("expected", "ok")
    if category == "violation":
        return ("violation", "err")
    return ("unexpected", "warn")


def _flatten_changes(diff, *, limit: int) -> list[str]:
    changes: list[str] = []
    changes.extend([f"+ {path}" for path in diff.added])
    changes.extend([f"~ {path}" for path in diff.modified])
    changes.extend([f"- {path}" for path in diff.deleted])
    return changes[:limit]


def _format_assertion_detail(assertion) -> Text:
    target = _format_assertion_target(assertion.target)
    if target:
        label = f"{assertion.name}({target})"
    else:
        label = assertion.name
    if assertion.reason:
        label = f"{label} — {assertion.reason}"
    return Text(label, style="val")


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
