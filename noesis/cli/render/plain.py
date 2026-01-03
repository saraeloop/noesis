from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from ..view_models import EpisodeDashboardVM, TimelineRowVM
from ..help_content import HelpScreen, HomeScreen, CommandGroup

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

        # Governance summary line (if present)
        gov = header.governance
        if gov:
            gov_parts = [f"governance: {gov.decision}"]
            if gov.rule_id:
                gov_parts.append(gov.rule_id)
            if gov.score is not None:
                gov_parts.append(f"score={gov.score:.2f}")
            gov_parts.append(f"enforced={str(gov.enforced).lower()}")
            print("  " + " ".join(gov_parts))

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

    def print_home(self, screen: HomeScreen) -> None:
        """Render home screen in plain mode - sparse bubbletea style."""
        if self.quiet:
            return

        # Header line with tagline
        print(f"Noesis v{screen.version}  {screen.tagline}")

        # Config line
        cfg = screen.config
        print(f"profile={cfg.governance_mode}  planner={cfg.planner_mode}  intuition={cfg.intuition_mode}  runs={cfg.runs_dir}")
        print()

        # Last episode (if any)
        if screen.last_episode:
            last = screen.last_episode
            print(f"last   {last.episode_id[:12]:<12}   {last.status:<8}   {last.duration}")
            print(f"task   {truncate(last.task, max_width=60)}")
            if last.status == "VETOED" and last.rule_id:
                score_str = f"score={last.score:.2f}" if last.score is not None else ""
                print(f"rule   {last.rule_id}   {score_str}")
                if last.message:
                    print(f"why    {truncate(last.message, max_width=60)}")
            print()

        # Next actions
        if screen.next_actions:
            print("next")
            for action in screen.next_actions[:3]:
                # Pad command to align descriptions
                cmd = action.command
                desc = action.description
                print(f"  {cmd:<40} {desc}")
            print()

        # Recent episodes (compact table)
        if screen.recent_episodes:
            print("recent")
            for ep in screen.recent_episodes[:5]:
                task_display = truncate(ep.task, max_width=45)
                print(f"  {ep.time_str:<5}  {ep.episode_short:<12}  {ep.status:<8}  {task_display}")
            print()

        # Footer
        print(f"help: {screen.footer_hint}")

    def print_help(self, screen: HelpScreen) -> None:
        """Render help screen in plain mode."""
        if self.quiet:
            return

        # Header
        print(f"Noēsis CLI {screen.version}")
        print(screen.tagline)
        print()
        print(f"Usage: {screen.usage}")
        print()

        # Command groups
        for group in screen.groups:
            print(group.title)
            max_name_len = max((len(cmd.name) for cmd in group.commands), default=0)
            for cmd in group.commands:
                print(f"  {cmd.name:<{max_name_len}}  {cmd.one_liner}")
            print()

        # Examples
        print("Examples")
        for example in screen.examples:
            print(f"  $ {example}")
        print()

        # Footer
        print(screen.footer)

    def print_command_help(self, text: str, *, title: str | None = None) -> None:
        if self.quiet:
            return
        if title:
            print(f"{title}")
            print("")
        print(text.rstrip())

    def print_explain(self, vm: Any) -> None:
        """Render explain output in plain mode."""
        if self.quiet:
            return

        print(f"Episode: {vm.episode_id}")
        print(f"Task: {vm.task}")
        print(f"Status: {vm.status.upper()}")

        if vm.governance:
            gov = vm.governance
            print()
            print("Governance Decision")
            print(f"  decision:  {gov.decision.upper()}")
            print(f"  enforced:  {gov.enforced}")
            print(f"  mode:      {gov.mode}")
            if gov.rule_id:
                print(f"  rule_id:   {gov.rule_id}")
            if gov.policy_id:
                print(f"  policy_id: {gov.policy_id}")
            if gov.score is not None:
                print(f"  score:     {gov.score:.2f}")
            if gov.message:
                print(f"  message:   {gov.message}")

        if vm.intuition_advice:
            print()
            print("Intuition Advice")
            for advice in vm.intuition_advice:
                conf = f" (confidence={advice.confidence:.2f})" if advice.confidence is not None else ""
                print(f"  - {advice.advice}{conf}")

        if vm.direction_blocks:
            print()
            print("Direction Blocks")
            for block in vm.direction_blocks:
                print(f"  - {block.status}: {block.reason}")
                if block.rule_id:
                    print(f"    rule: {block.rule_id}")

        if vm.risky_tokens:
            print()
            print(f"Risky Tokens: {', '.join(vm.risky_tokens)}")

        if vm.causal_chain:
            print()
            chain_str = " → ".join(
                f"{s.phase}({s.status})" if s.status else s.phase
                for s in vm.causal_chain
            )
            print(f"Causal Chain: {chain_str}")

        if vm.next_actions:
            print()
            print("Next Actions")
            for action in vm.next_actions:
                print(f"  $ {action}")


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


def _print_section(title: str, items: Iterable[str]) -> None:
    print(title)
    for item in items:
        print(f"  {item}")
    print("")


def _print_command_group(group: CommandGroup) -> None:
    print(group.title)
    max_len = max((len(cmd.name) for cmd in group.commands), default=0)
    for cmd in group.commands:
        print(f"  {cmd.name:<{max_len}}  {cmd.description}")
    print("")


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
