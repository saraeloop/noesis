from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from ..view_models import EpisodeDashboardVM, TimelineRowVM, build_verification_section
from ..help_content import HelpScreen, HomeScreen, CommandGroup

from ..formatters import format_ps_rows_for_plain, format_rows_for_plain, format_duration, truncate
from ..theme import outcome_badge, normalize_outcome

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
                process_id = row.get("process_id")
                if process_id:
                    print(process_id)
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
        filtered: List[TimelineRowVM] = []
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

        self.print_execution_map(view.execution_map, compact=False)
        self._print_verification_section(view)

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

    def print_run_summary(self, episode_id: str, task: str, summary: Dict[str, Any]) -> None:
        if self.quiet:
            print(episode_id)
            return
        print(f"Episode {episode_id}")
        print(f"Task: {task}")
        verification = build_verification_section(summary)
        print("\nSummary")
        print(f"  Agent    : {_format_agent_result(summary.get('adapter_result'))}")
        print(f"  Verify   : {_format_verify_result(verification)}")
        outcome = outcome_badge(summary.get("outcome"))
        print(f"  Outcome  : {outcome.label}")
        if verification.workspace_diff is not None:
            print(f"  Changed  : {_format_diff_counts(verification.workspace_diff)}")
        failure = _first_failed_assertion(verification)
        if failure:
            print(f"  First failure: {failure}")
        print(f"\nNext\n  -> noesis view {episode_id}      full details")

    def print_view_compact(self, view: EpisodeDashboardVM) -> None:
        header = view.header
        outcome = outcome_badge(view.verification.outcome.status)
        print(f"{outcome.label}  Episode {header.episode_id}")
        if header.task:
            print(f"Task: {header.task}")
        if header.duration is not None:
            print(f"Duration: {format_duration(header.duration)}")

        print("\nSummary")
        print(f"  Agent   : {_format_agent_result(view.verification.adapter_result)}")
        print(f"  Verify  : {_format_verify_result(view.verification)}")
        print(f"  Outcome : {outcome.label}")

        self.print_execution_map(view.execution_map, compact=True)
        _print_changed_files(view)

        if view.verification.assertions:
            print("\nAssertions")
            for assertion in view.verification.assertions:
                status = "PASS" if assertion.passed else "FAIL"
                detail = _format_assertion_detail(assertion)
                print(f"  {status} {detail}")

    def print_view_verbose(self, view: EpisodeDashboardVM) -> None:
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

        rows = self._filter_timeline(view.timeline_rows, None)
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

    def print_execution_map(self, execution_map, *, compact: bool = False) -> None:
        if self.quiet:
            return
        phases = execution_map.phases()
        if compact:
            parts = [f"{phase.phase}:{phase.status}" for phase in phases]
            print("Execution: " + " | ".join(parts))
            return
        print("\nExecution Map")
        for phase in phases:
            print(f"  {phase.phase:<7}: {phase.status}")

    def _print_verification_section(self, view: EpisodeDashboardVM) -> None:
        verification = view.verification
        print("\nVerification")
        print(f"  adapter_result : {verification.adapter_result or '—'}")
        outcome = verification.outcome.status or "—"
        if verification.outcome.summary:
            outcome = f"{outcome} ({verification.outcome.summary})"
        print(f"  outcome        : {outcome}")
        passed = "null" if verification.passed is None else str(verification.passed).lower()
        print(f"  passed         : {passed}")
        if verification.error:
            print(f"  error          : {verification.error}")
        diff = verification.workspace_diff
        if diff is None:
            print("  workspace_diff : —")
            print("  changed_files  : —")
        else:
            print(
                "  workspace_diff : "
                f"added={len(diff.added)} modified={len(diff.modified)} deleted={len(diff.deleted)}"
            )
            changed = _format_changed_files(diff, limit=10)
            print(f"  changed_files  : {changed or '—'}")
        failing = _first_failed_assertion(verification)
        print(f"  first_failure  : {failing or '—'}")

    def print_home(self, screen: HomeScreen) -> None:
        """Render the compact home screen."""
        if self.quiet:
            return
        from ..theme import NAV_ARROW_ASCII

        print(f"Noesis {screen.version}")
        print(screen.tagline)
        print()

        # Primary commands
        if screen.next_actions:
            print("Commands")
            for action in screen.next_actions[:3]:
                print(f"  {NAV_ARROW_ASCII}  {action.command:<40} {action.description}")
            print()

    def print_home_details(self, screen: HomeScreen) -> None:
        """Render the detailed home dashboard sections."""
        if self.quiet:
            return
        from ..theme import section_line_ascii

        width = 72

        cfg = screen.config
        print(f"governance {cfg.governance_mode}   planner {cfg.planner_mode}   intuition {cfg.intuition_mode}   runs {cfg.runs_dir}")
        print()

        if screen.last_episode:
            print(section_line_ascii("last", width))
            print()
            last = screen.last_episode
            outcome = normalize_outcome(last.outcome, status=last.status, success=last.success)
            badge = outcome_badge(outcome)
            print(f"  {badge.label:<16}   {last.episode_id[:12]:<12}   {last.duration}")
            print(f"    {truncate(last.task, max_width=60)}")
            if last.status == "VETOED" and last.rule_id:
                score_str = f"score={last.score:.2f}" if last.score is not None else ""
                print(f"    rule   {last.rule_id}   {score_str}")
                if last.message:
                    print(f"    why    {truncate(last.message, max_width=55)}")
            print()

        if screen.recent_episodes:
            print(section_line_ascii("recent", width))
            print()
            for ep in screen.recent_episodes[:5]:
                outcome = normalize_outcome(ep.outcome, status=ep.status, success=ep.success)
                badge = outcome_badge(outcome)
                task_display = truncate(ep.task, max_width=40)
                print(f"  {ep.time_str:<5}  {badge.label:<16}  {ep.episode_short:<12}  {task_display}")
            print()

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
        """Render explain output in plain mode - modern ASCII style."""
        if self.quiet:
            return
        from ..theme import section_line_ascii, status_symbol, NAV_ARROW_ASCII, BULLET_ASCII

        width = 72

        # Episode header section
        print(section_line_ascii(vm.episode_id, width))
        print()

        # Status with symbol
        sym = status_symbol(vm.status, ascii_mode=True)
        enforced_str = "   enforced" if vm.governance and vm.governance.enforced else ""
        print(f"  {sym} {vm.status.upper()}{enforced_str}")
        print()

        # Task
        print(f"  Task: {truncate(vm.task, max_width=65)}")
        print()

        # Governance Decision section
        if vm.governance:
            gov = vm.governance
            print(section_line_ascii("governance", width))
            print()
            enforced_tag = " (enforced)" if gov.enforced else ""
            print(f"  decision   {gov.decision.upper()}{enforced_tag}")
            print(f"  mode       {gov.mode}")
            if gov.rule_id:
                print(f"  rule       {gov.rule_id}")
            if gov.policy_id:
                version_str = f" v{gov.policy_version}" if gov.policy_version else ""
                print(f"  policy     {gov.policy_id}{version_str}")
            if gov.score is not None:
                print(f"  score      {gov.score:.2f}")
            if gov.message:
                print(f"  message    {gov.message}")
            print()

        # Evidence section
        if vm.intuition_advice or vm.direction_blocks or vm.risky_tokens:
            print(section_line_ascii("evidence", width))
            print()

            if vm.intuition_advice:
                print("  Intuition Advice")
                for advice in vm.intuition_advice:
                    conf = f" (confidence={advice.confidence:.2f})" if advice.confidence is not None else ""
                    print(f"    {BULLET_ASCII}  {advice.advice}{conf}")
                print()

            if vm.direction_blocks:
                print("  Direction Blocks")
                for block in vm.direction_blocks:
                    print(f"    {BULLET_ASCII}  {block.status}: {block.reason}")
                    if block.rule_id:
                        print(f"       rule: {block.rule_id}")
                print()

            if vm.risky_tokens:
                print("  Risky Tokens")
                print(f"    {BULLET_ASCII}  {', '.join(vm.risky_tokens)}")
                print()

        # Causal Chain section
        if vm.causal_chain:
            print(section_line_ascii("causal chain", width))
            print()
            chain_str = " -> ".join(
                f"{s.phase}({s.status})" if s.status else s.phase
                for s in vm.causal_chain
            )
            print(f"  {chain_str}")
            print()

        # Next Actions section
        if vm.next_actions:
            print(section_line_ascii("next", width))
            print()
            for action in vm.next_actions:
                print(f"  {NAV_ARROW_ASCII}  {action}")
            print()

        # Closing separator
        print("-" * width)


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


def _format_agent_result(adapter_result: object) -> str:
    if adapter_result == "success":
        return "OK"
    if adapter_result == "error":
        return "FAIL"
    if adapter_result == "skipped":
        return "SKIPPED"
    return "UNKNOWN"


def _format_verify_result(verification) -> str:
    total = len(verification.assertions)
    passed = sum(1 for assertion in verification.assertions if assertion.passed)
    if verification.passed is True:
        return f"PASSED ({passed} of {total})" if total else "PASSED"
    if verification.passed is False:
        return f"FAILED ({passed} of {total})" if total else "FAILED"
    if verification.error:
        return f"ERROR ({verification.error})"
    if verification.provided is False:
        return "SKIPPED"
    return "UNVERIFIED"


def _format_diff_counts(diff) -> str:
    if diff is None:
        return "—"
    return f"+ {len(diff.added)} added   ~ {len(diff.modified)} modified   - {len(diff.deleted)} deleted"


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


def _format_assertion_detail(assertion) -> str:
    target = _format_assertion_target(assertion.target)
    if target:
        label = f"{assertion.name}({target})"
    else:
        label = assertion.name
    if assertion.reason:
        label = f"{label} — {assertion.reason}"
    return label


def _print_changed_files(view: EpisodeDashboardVM, *, limit: int = 10) -> None:
    diff = view.verification.workspace_diff
    if diff is None:
        return
    print("\nChanged Files")
    category = _change_category(view.verification)
    label = _change_label(category)
    for change in _flatten_changes(diff, limit=limit):
        print(f"  {change:<30}  {label}")


def _change_category(verification) -> str:
    if verification.passed is True:
        return "expected"
    if verification.passed is False:
        return "violation"
    return "unexpected"


def _change_label(category: str) -> str:
    if category == "expected":
        return "expected"
    if category == "violation":
        return "violation"
    return "unexpected"


def _flatten_changes(diff, *, limit: int) -> list[str]:
    changes: list[str] = []
    changes.extend([f"+ {path}" for path in diff.added])
    changes.extend([f"~ {path}" for path in diff.modified])
    changes.extend([f"- {path}" for path in diff.deleted])
    return changes[:limit]


def _format_assertion_target(target) -> str | None:
    if isinstance(target, tuple):
        return "[" + ", ".join(target) + "]"
    if isinstance(target, str):
        return target
    return None


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
