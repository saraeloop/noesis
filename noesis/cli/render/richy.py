from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from ..viewer import EpisodeView, TimelineRow, ValidationIssue


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
        table.add_column("TASK", style="val")
        for row in rows:
            table.add_row(
                (row.get("started_at", "")[:25]),
                (row.get("episode_id", "")[:28]),
                row.get("task", ""),
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

    def _filter_timeline(self, rows: Iterable[TimelineRow], grep: str | None) -> list[TimelineRow]:
        if not grep:
            return list(rows)
        terms = [term.strip().lower() for term in grep.split() if term.strip()]
        filtered: list[TimelineRow] = []
        for row in rows:
            haystack = f"phase={row.phase} agent={row.agent} note={row.note}".lower()
            if all(term in haystack for term in terms):
                filtered.append(row)
        return filtered

    def _render_validation(self, issues: Iterable[ValidationIssue]) -> None:
        issues = list(issues)
        if not issues:
            return
        body = "\n".join(f"[err]•[/] {issue.format()}" for issue in issues)
        self.console.print(Panel(body, title="[title]Validation[/]", border_style="red"))

    def print_viewer(self, view: EpisodeView, *, grep: str | None = None) -> None:
        header = view.header
        header_table = Table.grid(padding=(0, 1))
        header_table.add_row(Text("episode_id", style="key"), Text(str(header.get("episode_id")), style="val"))
        header_table.add_row(Text("started_at", style="key"), Text(str(header.get("started_at")), style="val"))
        header_table.add_row(Text("planner_mode", style="key"), Text(str(header.get("planner_mode")), style="val"))
        intuition = "on" if header.get("intuition_enabled") else "off"
        header_table.add_row(Text("intuition", style="key"), Text(intuition, style="val"))
        if header.get("using"):
            header_table.add_row(Text("using", style="key"), Text(str(header.get("using")), style="val"))
        policies = header.get("policies") or []
        if policies:
            header_table.add_row(Text("policies", style="key"), Text(", ".join(str(p) for p in policies), style="val"))
        ports = header.get("ports")
        if isinstance(ports, dict) and ports:
            ports_text = ", ".join(f"{k}={v}" for k, v in ports.items())
            header_table.add_row(Text("ports", style="key"), Text(ports_text, style="muted"))
        self.console.print(Panel(header_table, title="[title]Episode[/]"))

        kpis = view.kpis
        kpi_table = Table.grid(padding=(0, 1))
        kpi_table.add_row(Text("success", style="key"), Text(str(kpis.get("success")), style="ok" if kpis.get("success") else "err"))
        kpi_table.add_row(Text("plan_adherence", style="key"), Text(str(kpis.get("plan_adherence")), style="val"))
        kpi_table.add_row(Text("veto_count", style="key"), Text(str(kpis.get("veto_count")), style="val"))
        kpi_table.add_row(Text("tool_coverage", style="key"), Text(str(kpis.get("tool_coverage")), style="val"))
        phase_ms = kpis.get("phase_ms") or {}
        if phase_ms:
            phase_table = Table.grid(padding=(0, 1))
            for phase, value in phase_ms.items():
                phase_table.add_row(Text(phase, style="key"), Text(f"{value} ms", style="val"))
            kpi_table.add_row(Text("phase_ms", style="key"), phase_table)
        self.console.print(Panel(kpi_table, title="[title]KPIs[/]"))

        if view.governance:
            gov = view.governance
            gov_table = Table.grid(padding=(0, 1))
            gov_table.add_row(Text("decision", style="key"), Text(str(gov.get("decision")), style="val"))
            gov_table.add_row(Text("rule_id", style="key"), Text(str(gov.get("rule_id")), style="val"))
            if gov.get("policy_id"):
                policy = f"{gov.get('policy_id')}@{gov.get('policy_version')}" if gov.get("policy_version") else gov.get("policy_id")
                gov_table.add_row(Text("policy", style="key"), Text(str(policy), style="val"))
            if gov.get("message"):
                gov_table.add_row(Text("message", style="key"), Text(str(gov.get("message")), style="val"))
            if gov.get("time_to_veto_ms") is not None:
                gov_table.add_row(Text("time_to_veto_ms", style="key"), Text(str(gov.get("time_to_veto_ms")), style="val"))
            self.console.print(Panel(gov_table, title="[title]Governance[/]", border_style="yellow"))

        rows = self._filter_timeline(view.timeline, grep)
        timeline_table = Table(
            show_header=True,
            header_style="title",
            box=None,
            expand=True,
            pad_edge=False,
        )
        timeline_table.add_column("TS", style="muted", no_wrap=True)
        timeline_table.add_column("Δ", style="muted", no_wrap=True)
        timeline_table.add_column("PHASE", style="val", no_wrap=True)
        timeline_table.add_column("AGENT", style="muted", no_wrap=True)
        timeline_table.add_column("NOTE", style="val")

        if not rows:
            timeline_table.add_row("-", "-", "-", "-", "no events matched")
        else:
            for row in rows:
                phase_style = f"phase.{row.phase}" if f"phase.{row.phase}" in self.console.theme.styles else "val"
                timeline_table.add_row(
                    row.timestamp or "",
                    row.delta_label(),
                    Text(row.phase, style=phase_style),
                    Text(row.agent, style="muted"),
                    Text(row.note or "", style="val"),
                )
        self.console.print(timeline_table)

        self._render_validation(view.validation)
