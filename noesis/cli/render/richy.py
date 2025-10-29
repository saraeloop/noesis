from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax


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
