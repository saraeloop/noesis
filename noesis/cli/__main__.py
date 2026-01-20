from __future__ import annotations

from pathlib import Path
from typing import Optional
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout, redirect_stderr

import typer

from noesis.cli.context import GlobalOptions, build_context
from noesis.cli.render.plain import PlainRenderer
from noesis.cli.render.richy import RichRenderer
from noesis.cli.theme import build_theme_tokens, outcome_badge, normalize_outcome
from noesis.cli.verification_input import parse_verify_args
from noesis.cli.view_models import (
    build_episode_dashboard,
    build_episode_dashboard_from_payloads,
)
from noesis.cli.formatters import format_duration
from noesis.cli.query import load_episode_dir
from noesis.cli.content.home import build_home_screen, RecentEpisode, LastEpisodeInfo
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION
from noesis.runtime.paths import resolve_noesis_paths
from noesis.infrastructure.layout_migration import migrate_layout
from noesis.infrastructure.process_registry import FileProcessRegistry


try:  # pragma: no cover - optional Rich import
    from rich.console import Console
    from rich.theme import Theme
    _HAS_RICH = True
except Exception:  # noqa: BLE001
    Console = None  # type: ignore[assignment]
    Theme = None  # type: ignore[assignment]
    _HAS_RICH = False


app = typer.Typer(
    name="noesis",
    help="Noesis CLI — run, verify, and inspect episodes.",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_CLI_SCHEMA_VERSION = "cli/1.1"
_CLI_COMPAT_MIN = "cli/1.0"
_CLI_COMPAT_MAX = "cli/1.x"
_CLI_VERSION_RE = re.compile(r"^cli/(?P<major>\d+)\.(?P<minor>\d+|x)$")
_LAST_ARGV: list[str] | None = None

# Valid outcome values per ADR-010 (verification layer)
_VALID_OUTCOMES = frozenset({"success", "success_unverified", "goal_not_achieved", "error"})


def _select_renderer(ctx, *, json_output: bool, quiet: bool, force_rich: bool):
    if json_output or quiet or os.environ.get("NO_COLOR"):
        return PlainRenderer(quiet=quiet)
    if not _HAS_RICH:
        return PlainRenderer(quiet=quiet)
    if not ctx.isatty and not force_rich:
        return PlainRenderer(quiet=quiet)
    theme_tokens = build_theme_tokens()
    console = Console(
        theme=Theme(theme_tokens.styles),
        force_terminal=force_rich,
        soft_wrap=True,
    )
    return RichRenderer(console, quiet=quiet)


def _fetch_recent_episodes(ctx, *, limit: int = 5) -> list[RecentEpisode]:
    try:
        rows = ctx.ns.list_runs(limit=limit, context=ctx.runtime_context)
    except Exception:  # noqa: BLE001
        return []

    episodes: list[RecentEpisode] = []
    for row in rows:
        try:
            success_val = row.get("success")
            success = None
            if isinstance(success_val, bool):
                success = success_val
            elif isinstance(success_val, int):
                success = bool(success_val)
            started_at = row.get("started_at") or ""
            time_str = started_at[11:16] if len(started_at) >= 16 else "--:--"
            episode_id = row.get("episode_id", "") or ""
            task = row.get("task", "") or ""
            outcome = normalize_outcome(
                row.get("outcome"),
                status=row.get("status"),
                success=row.get("success"),
            )
            status_label = outcome_badge(outcome).label
            episodes.append(
                RecentEpisode(
                    time_str=time_str or "--:--",
                    episode_short=episode_id[:12] if len(episode_id) > 12 else (episode_id or "—"),
                    episode_id=episode_id,
                    status=status_label,
                    task=(task[:50] + "…" if len(task) > 50 else task) or "(no task)",
                    duration=format_duration(row.get("duration_sec")) or "—",
                    outcome=outcome,
                    success=success,
                )
            )
        except Exception:  # noqa: BLE001
            continue
    return episodes


def _fetch_last_episode_info(ctx, recent: list[RecentEpisode]) -> LastEpisodeInfo | None:
    if not recent:
        return None
    last = recent[0]
    rule_id = None
    score = None
    message = None
    try:
        events = list(ctx.ns.events.read(last.episode_id, context=ctx.runtime_context))
        for evt in events:
            payload = evt.get("payload", {}) if isinstance(evt, dict) else {}
            # Governance decisions carry veto metadata
            if evt.get("phase") == "governance":
                rule_id = payload.get("rule_id") or payload.get("details", {}).get("rule_id")
                score = payload.get("score")
                message = payload.get("message") or payload.get("details", {}).get("reason")
                break
    except Exception:  # noqa: BLE001
        pass
    return LastEpisodeInfo(
        episode_id=last.episode_id,
        status=last.status,
        duration=last.duration,
        task=last.task,
        outcome=last.outcome,
        success=last.success,
        rule_id=rule_id,
        score=score,
        message=message,
    )


def _render_home(
    renderer,
    ctx,
    *,
    show_details: bool = True,
    prompt_for_details: bool = False,
) -> None:
    recent = _fetch_recent_episodes(ctx)
    last_episode_id = recent[0].episode_id if recent else None
    last_episode_info = _fetch_last_episode_info(ctx, recent)
    config_mapping = ctx.config_snapshot.to_mapping() if hasattr(ctx.config_snapshot, "to_mapping") else {}
    screen = build_home_screen(
        ctx.version,
        config_snapshot=config_mapping,
        recent_episodes=recent,
        last_episode_id=last_episode_id,
        last_episode_info=last_episode_info,
    )
    renderer.print_home(screen)

    if show_details:
        renderer.print_home_details(screen)


def _normalize_cli_version(requested: str | None) -> tuple[str | None, int | None, str | None]:
    if requested is None:
        return _CLI_SCHEMA_VERSION, None, None
    match = _CLI_VERSION_RE.match(requested.strip())
    if not match:
        return None, 2, "invalid cli version (expected cli/MAJOR.MINOR)"
    major = int(match.group("major"))
    if major != 1:
        return None, 3, "unsupported cli version"
    return _CLI_SCHEMA_VERSION, None, None


def _build_run_envelope(
    *,
    episode_id: str,
    episode_dir: Path,
    summary: dict,
    workspace: Path | None,
    verify_provided: bool,
    argv: list[str],
) -> dict[str, object]:
    """Build the cli/1.0 RunResult envelope per ADR-011.

    The Go UI MUST use this envelope for artifact paths.
    Scanning the filesystem is forbidden for run boundary integration.

    Required fields: cli, episode_id, episode_dir, artifacts, outcome, adapter_result, capabilities
    Optional fields: verification, invocation
    """
    # Validate outcome against ADR-010 (defense-in-depth)
    outcome = summary.get("outcome")
    if outcome and outcome not in _VALID_OUTCOMES:
        sys.stderr.write(f"warning: unexpected outcome '{outcome}' in summary\n")

    verification = summary.get("verification") if isinstance(summary.get("verification"), dict) else {}
    capabilities: list[str] = ["execution_map"]
    if isinstance(verification, dict):
        capabilities.append("verification")
        if verification.get("workspace_diff") is not None:
            capabilities.append("workspace_diff")
        if verification.get("snapshots") is not None:
            capabilities.append("snapshots")

    artifacts: dict[str, object] = {}
    for name in ("summary.json", "events.jsonl", "state.json", "manifest.json"):
        path = episode_dir / name
        if path.exists():
            key = name.split(".")[0]
            artifacts[key] = name

    invocation: dict[str, object] = {
        "argv": argv,
        "verify_provided": verify_provided,
    }
    if workspace is not None:
        invocation["workspace"] = str(workspace)

    envelope = {
        "cli": {
            "schema_version": _CLI_SCHEMA_VERSION,
            "compat_min": _CLI_COMPAT_MIN,
            "compat_max": _CLI_COMPAT_MAX,
        },
        "episode_id": episode_id,
        "episode_dir": str(episode_dir),
        "artifacts": artifacts,
        "summary_schema_version": summary.get("schema_version", SUMMARY_SCHEMA_VERSION),
        "outcome": outcome,
        "adapter_result": summary.get("adapter_result"),
        "verification": {
            "provided": verification.get("provided"),
            "passed": verification.get("passed"),
            "error": verification.get("error"),
        },
        "capabilities": sorted(set(capabilities)),
        "invocation": invocation,
    }
    process_block = summary.get("process")
    if isinstance(process_block, dict):
        envelope["process"] = process_block
    return envelope


def _build_view_envelope(
    *,
    episode_id: str,
    episode_dir_path: Path | None,
    dashboard: dict,
) -> dict[str, object]:
    """Build the cli/1.1 ViewResult envelope per ADR-012."""
    artifacts: dict[str, str] = {}
    episode_dir_str: str | None = None
    if episode_dir_path is not None and episode_dir_path.exists():
        episode_dir_str = str(episode_dir_path)
        for name in ("summary.json", "events.jsonl", "state.json", "manifest.json"):
            path = episode_dir_path / name
            if path.exists():
                key = name.split(".")[0]
                artifacts[key] = name
    return {
        "cli": {
            "schema_version": _CLI_SCHEMA_VERSION,
            "compat_min": _CLI_COMPAT_MIN,
            "compat_max": _CLI_COMPAT_MAX,
        },
        "episode_id": episode_id,
        "episode_dir": episode_dir_str,
        "artifacts": artifacts,
        "dashboard": dashboard,
    }


def _build_ps_envelope(
    *,
    episodes: list[dict],
    limit: int,
    offset: int = 0,
) -> dict[str, object]:
    """Build the cli/1.1 PsResult envelope."""
    return {
        "cli": {
            "schema_version": _CLI_SCHEMA_VERSION,
            "compat_min": _CLI_COMPAT_MIN,
            "compat_max": _CLI_COMPAT_MAX,
        },
        "episodes": episodes,
        "total_count": len(episodes),
        "limit": limit,
        "offset": offset,
    }


def _build_processes_envelope(
    *,
    processes: list[dict],
    limit: int,
    offset: int = 0,
) -> dict[str, object]:
    """Build the cli/1.1 ProcessesResult envelope."""
    return {
        "cli": {
            "schema_version": _CLI_SCHEMA_VERSION,
            "compat_min": _CLI_COMPAT_MIN,
            "compat_max": _CLI_COMPAT_MAX,
        },
        "processes": processes,
        "total_count": len(processes),
        "limit": limit,
        "offset": offset,
    }


def _filter_runs_by_process(rows: list[dict], process: str | None) -> list[dict]:
    """Return rows whose process id or name matches the requested process."""
    if not process:
        return rows
    target = process.strip()
    if not target:
        return rows
    filtered: list[dict] = []
    for row in rows:
        proc = row.get("process") if isinstance(row, dict) else None
        if not isinstance(proc, dict):
            continue
        pid = str(proc.get("id") or "")
        pname = str(proc.get("name") or proc.get("process_name") or "")
        if target in {pid, pname}:
            filtered.append(row)
    return filtered


def _build_events_envelope(
    *,
    episode_id: str,
    events: list[dict],
    phase_filter: str | None = None,
) -> dict[str, object]:
    """Build the cli/1.1 EventsResult envelope per ADR-012."""
    return {
        "cli": {
            "schema_version": _CLI_SCHEMA_VERSION,
            "compat_min": _CLI_COMPAT_MIN,
            "compat_max": _CLI_COMPAT_MAX,
        },
        "episode_id": episode_id,
        "events": events,
        "filters": {"phase": phase_filter},
        "event_count": len(events),
    }


@app.callback(invoke_without_command=True)
def home(
    typer_ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
    full: bool = typer.Option(False, "--full", help="Show the full home dashboard"),
) -> None:
    if typer_ctx.invoked_subcommand:
        return
    options = GlobalOptions(verbose=verbose, quiet=quiet, json=json_output, force_rich=force_rich)
    options.normalize()
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    # Only show detailed home when explicitly requested via --full
    show_details = bool(full)
    _render_home(renderer, ctx, show_details=show_details, prompt_for_details=False)


@app.command()
def run(
    task: str = typer.Argument(..., help="Task prompt"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", help="Workspace root for verification"),
    process: Optional[str] = typer.Option(None, "--process", help="Process label for grouping runs"),
    verify_file: Optional[Path] = typer.Option(None, "--verify-file", help="JSON file of verification specs"),
    verify_file_exists: Optional[list[str]] = typer.Option(None, "--verify-file-exists", help="Require file exists"),
    verify_file_contains: Optional[list[str]] = typer.Option(None, "--verify-file-contains", help="Require file contains text"),
    text: Optional[list[str]] = typer.Option(None, "--text", help="Text for --verify-file-contains"),
    verify_only_modified: Optional[list[str]] = typer.Option(None, "--verify-only-modified", help="Only modified paths"),
    verify_no_modifications: bool = typer.Option(False, "--verify-no-modifications", help="Require no modifications"),
    planner: Optional[str] = typer.Option(None, "--planner", help="Planner mode override (minimal|meta)"),
    cli_version: Optional[str] = typer.Option(None, "--cli-version", help="CLI envelope version (cli/1.0)"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(verbose=verbose, quiet=quiet, json=json_output, force_rich=force_rich)
    options.normalize()
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)

    try:
        verify = parse_verify_args(
            verify_file=str(verify_file) if verify_file else None,
            verify_file_exists=verify_file_exists,
            verify_file_contains=verify_file_contains,
            verify_texts=text,
            verify_only_modified=verify_only_modified,
            verify_no_modifications=verify_no_modifications,
        )
    except ValueError as exc:
        sys.stderr.write(f"usage error: {exc}\n")
        raise typer.Exit(code=2)
    if json_output:
        try:
            import click

            click_ctx = click.get_current_context(silent=True)
            if click_ctx is not None and cli_version is None:
                cli_version = click_ctx.params.get("cli_version")
        except Exception:  # noqa: BLE001
            pass
        _version, error_code, version_error = _normalize_cli_version(cli_version)
        if version_error:
            sys.stderr.write(f"{version_error}\n")
            raise typer.Exit(code=error_code or 3)

    prior_planner = None
    planner_changed = False
    if planner:
        prior_planner = getattr(getattr(ctx, "config_snapshot", None), "planner_mode", None)
        if hasattr(prior_planner, "value"):
            prior_planner = prior_planner.value
        ctx.ns.set(context=ctx.runtime_context, planner_mode=planner)
        planner_changed = True
    try:
        episode_id = ctx.ns.run(
            task=task,
            context=ctx.runtime_context,
            workspace=str(workspace) if workspace else None,
            process=process,
            verify=verify,
        )
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"runner error: {exc}\n")
        raise typer.Exit(code=3)
    finally:
        if planner_changed:
            ctx.ns.set(context=ctx.runtime_context, planner_mode=prior_planner)
    summary = ctx.ns.summary.read(episode_id, context=ctx.runtime_context)
    if not isinstance(summary, dict):
        sys.stderr.write("runner error: missing summary\n")
        raise typer.Exit(code=3)

    if json_output:
        layout = resolve_noesis_paths(
            workspace=workspace.expanduser().resolve() if workspace else None,
            runs_dir=ctx.config_snapshot.runs_dir,
        )
        episode_dir = layout.episodes_dir / episode_id
        envelope = _build_run_envelope(
            episode_id=episode_id,
            episode_dir=episode_dir,
            summary=summary,
            workspace=workspace.expanduser().resolve() if workspace else None,
            verify_provided=bool(verify),
            argv=["noesis", "run", task],
        )
        payload = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
        sys.stdout.write(payload + "\n")
        outcome = summary.get("outcome")
        if outcome in {"success", "success_unverified"}:
            raise typer.Exit(code=0)
        raise typer.Exit(code=1)

    renderer.print_run_summary(episode_id, task, summary)


@app.command()
def view(
    episode_id: str = typer.Argument(..., help="Episode ID or run directory"),
    verbose: bool = typer.Option(False, "--verbose", help="Show KPIs, phases, and timeline"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(verbose=verbose, quiet=quiet, json=json_output, force_rich=force_rich)
    options.normalize()
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)

    target = Path(episode_id).expanduser()
    if target.exists():
        ep_dir = target if target.is_dir() else target.parent
        vm = build_episode_dashboard(ep_dir, validate=False)
    else:
        ep_dir = load_episode_dir(episode_id, ctx.config_snapshot.runs_dir)
        if ep_dir.exists():
            vm = build_episode_dashboard(ep_dir, validate=False)
        else:
            try:
                summary = ctx.ns.summary.read(episode_id, context=ctx.runtime_context)
                events = list(ctx.ns.events.read(episode_id, context=ctx.runtime_context))
            except Exception as exc:  # noqa: BLE001
                renderer.echo(f"episode not found: {episode_id}")
                if not quiet:
                    renderer.echo(f"  {exc}")
                raise typer.Exit(code=1)
            vm = build_episode_dashboard_from_payloads(
                summary=summary,
                events=events,
                episode_id=episode_id,
                validate=False,
            )
    if json_output:
        envelope = _build_view_envelope(
            episode_id=vm.header.episode_id if vm.header else episode_id,
            episode_dir_path=ep_dir if ep_dir.exists() else None,
            dashboard=vm.to_dict(),
        )
        sys.stdout.write(json.dumps(envelope) + "\n")
        return
    renderer.print_view_compact(vm)
    if verbose:
        renderer.print_view_verbose(vm)


@app.command()
def ps(
    limit: int = typer.Option(20, "--limit", help="Number of episodes to show"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
    process: Optional[str] = typer.Option(None, "--process", help="Filter episodes by process id or name"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    rows = ctx.ns.list_runs(limit=None if process else limit, context=ctx.runtime_context)
    episodes = _filter_runs_by_process(rows, process)
    if limit is not None:
        episodes = episodes[:limit]
    if json_output:
        envelope = _build_ps_envelope(episodes=episodes, limit=limit)
        sys.stdout.write(json.dumps(envelope) + "\n")
        return
    renderer.print_list(episodes, quiet=quiet)


@app.command()
def processes(
    limit: int = typer.Option(20, "--limit", help="Number of processes to show"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
    process: Optional[str] = typer.Option(None, "--process", help="Filter processes by id or name"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    layout = resolve_noesis_paths(workspace=None, runs_dir=ctx.config_snapshot.runs_dir)
    registry = FileProcessRegistry(layout.processes_dir)
    records = registry.list()
    if process:
        target = process.strip()
        records = [
            item for item in records if item.process_id == target or item.process_name == target
        ]
    records = sorted(records, key=lambda item: item.last_seen_at, reverse=True)[:limit]
    process_rows: list[dict[str, object]] = []
    for record in records:
        process_rows.append(
            {
                "process_id": record.process_id,
                "process_name": record.process_name,
                "kind": record.kind,
                "status": record.status,
                "last_seen_at": record.last_seen_at.isoformat(),
                "active_run_id": record.active_run_id,
                "last_run_outcome": record.last_run_outcome,
            }
        )
    if json_output:
        envelope = _build_processes_envelope(processes=process_rows, limit=limit)
        sys.stdout.write(json.dumps(envelope) + "\n")
        return
    renderer.print_ps(process_rows, quiet=quiet)


@app.command()
def runs(
    process: str = typer.Option(..., "--process", help="Process name or id"),
    limit: int = typer.Option(20, "--limit", help="Number of runs to show"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    rows = ctx.ns.list_runs(limit=None, context=ctx.runtime_context)
    filtered = _filter_runs_by_process(rows, process)
    if limit is not None:
        filtered = filtered[:limit]
    if json_output:
        sys.stdout.write(json.dumps(filtered) + "\n")
        return
    renderer.print_list(filtered, quiet=quiet)


@app.command()
def browse(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    try:
        from noesis.cli.tui.browse import run_browse
    except Exception as exc:  # noqa: BLE001
        renderer.echo(f"Textual not available: {exc}")
        raise typer.Exit(code=1)
    episodes = ctx.ns.list_runs(limit=50, context=ctx.runtime_context)
    layout = resolve_noesis_paths(workspace=None, runs_dir=ctx.config_snapshot.runs_dir)
    run_browse(episodes, episode_roots=layout.episode_roots())


@app.command()
def events(
    episode_id: str = typer.Argument(..., help="Episode identifier"),
    phase: Optional[str] = typer.Option(
        None,
        "--phase",
        help="Filter by phase (start/observe/plan/act/reflect/insight/terminate/error)",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress banner"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (JSONL streaming)"),
    envelope: bool = typer.Option(False, "--envelope", help="JSON envelope output (single object, per ADR-012)"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output or envelope, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])

    # Read events (shared by envelope and JSONL modes)
    try:
        all_events = list(ctx.ns.events.read(episode_id, context=ctx.runtime_context))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: {exc}\n")
        raise typer.Exit(code=1)

    # Apply phase filter if specified
    if phase:
        all_events = [e for e in all_events if e.get("phase") == phase]

    # Envelope mode: single JSON envelope per ADR-012
    if envelope:
        result = _build_events_envelope(
            episode_id=episode_id,
            events=all_events,
            phase_filter=phase,
        )
        sys.stdout.write(json.dumps(result) + "\n")
        return

    # JSONL streaming mode: one compact JSON line per event (backward compat)
    if json_output:
        for event in all_events:
            sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")
        return

    # Human-readable output: delegate to argparse command
    from argparse import Namespace
    from noesis.cli.commands.events import COMMAND as EVENTS

    renderer = _select_renderer(ctx, json_output=False, quiet=quiet, force_rich=force_rich)
    args = Namespace(episode_id=episode_id, phase=phase, quiet=quiet, json=False)
    exit_code = EVENTS.run(args, ctx, renderer)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command()
def insight(
    episode_id: str = typer.Argument(..., help="Episode identifier"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress banner"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    from argparse import Namespace
    from noesis.cli.commands.insight import COMMAND as INSIGHT

    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    args = Namespace(episode_id=episode_id, phase="insight", quiet=quiet, json=json_output)
    exit_code = INSIGHT.run(args, ctx, renderer)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("validate-ports")
def validate_ports(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    from argparse import Namespace
    from noesis.cli.commands.validate_ports import COMMAND as VALIDATE

    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    args = Namespace(quiet=quiet, json=json_output)
    exit_code = VALIDATE.run(args, ctx, renderer)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command()
def diagnostics(
    mode: Optional[str] = typer.Argument(None, help="Optional subcommand: replay"),
    run_a: Optional[Path] = typer.Argument(None, help="First run directory"),
    run_b: Optional[Path] = typer.Argument(None, help="Second run directory"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero on warnings"),
    checks: Optional[str] = typer.Option(None, "--checks", help="Comma-separated list of checks"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    from argparse import Namespace
    import click
    from noesis.cli.commands.diagnostics import COMMAND as DIAGNOSTICS

    if _LAST_ARGV is not None and "--strict" in _LAST_ARGV:
        strict = True
    if mode == "--strict":
        mode = None
        strict = True

    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    try:
        config_port = ctx.runtime_context.require(
            "config",
            getattr(ctx.runtime_context.config_port, "__api_version__", "config/1.0-rc1"),
        )
        ctx.config_snapshot = config_port.get()
    except Exception:  # noqa: BLE001
        pass
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    click_ctx = click.get_current_context(silent=True)
    if click_ctx is not None:
        if "strict" in click_ctx.params:
            strict_param = click_ctx.params.get("strict")
            if strict_param is not None:
                strict = bool(strict_param) or strict
    if not strict and _LAST_ARGV is not None and "--strict" in _LAST_ARGV:
        strict = True
    args = Namespace(
        mode=mode,
        run_a=str(run_a) if run_a else None,
        run_b=str(run_b) if run_b else None,
        quiet=quiet,
        json=json_output,
        strict=strict,
        checks=checks,
    )
    exit_code = DIAGNOSTICS.run(args, ctx, renderer)
    # Skip additional strict checks in replay mode - replay has its own exit code logic
    if mode == "replay":
        if exit_code:
            raise typer.Exit(code=exit_code)
        return
    strict_argv = _LAST_ARGV is not None and "--strict" in _LAST_ARGV
    if (strict or strict_argv) and exit_code == 0:
        try:
            snapshot = ctx.config_snapshot
            if snapshot is not None:
                learn_home = getattr(snapshot, "learn_home", None)
                if learn_home and not Path(str(learn_home)).expanduser().exists():
                    exit_code = 1
        except Exception:  # noqa: BLE001
            pass
    if (strict or strict_argv) and exit_code == 0:
        try:
            from noesis.runtime.config_provider import get_config_snapshot

            snapshot = get_config_snapshot()
            learn_home = getattr(snapshot, "learn_home", None)
            if learn_home is None:
                learn_home = getattr(ctx.config_snapshot, "learn_home", None) or ctx.ns.get().get("learn_home")
            if learn_home and not Path(str(learn_home)).expanduser().exists():
                exit_code = 1
        except Exception:  # noqa: BLE001
            pass
        if exit_code == 0:
            try:
                checks = list(DIAGNOSTICS._run_checks(ctx.config_snapshot, ctx.runtime_context.list_ports()))
                overall = DIAGNOSTICS._overall_status(checks)
                if overall == "warn":
                    exit_code = 1
            except Exception:  # noqa: BLE001
                pass
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("migrate-layout")
def migrate_layout_cmd(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    layout = resolve_noesis_paths(workspace=None, runs_dir=ctx.config_snapshot.runs_dir)
    result = migrate_layout(layout)
    if json_output:
        renderer.json(result.to_dict())
        return
    renderer.banner("Noesis layout migration")
    renderer.echo(f"root      : {layout.root}")
    renderer.echo(f"episodes  : {result.episodes_copied}")
    renderer.echo(f"processes : {result.processes_copied}")
    if result.warnings:
        renderer.echo("warnings  :")
        for warning in result.warnings:
            renderer.echo(f"  - {warning}")


@app.command()
def explain(
    episode_id: str = typer.Argument(..., help="Episode identifier"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    force_rich: bool = typer.Option(False, "--force-rich", help="Force Rich output"),
    port: Optional[list[str]] = typer.Option(None, "--port", help="Register runtime port (NAME=SPEC)"),
) -> None:
    from argparse import Namespace
    from noesis.cli.commands.explain import COMMAND as EXPLAIN

    options = GlobalOptions(quiet=quiet, json=json_output, force_rich=force_rich)
    ctx = build_context(options, port_specs=port or [])
    renderer = _select_renderer(ctx, json_output=json_output, quiet=quiet, force_rich=force_rich)
    args = Namespace(episode_id=episode_id, quiet=quiet, json=json_output)
    exit_code = EXPLAIN.run(args, ctx, renderer)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command()
def help(
    command: Optional[str] = typer.Argument(None, help="Command to show help for"),
) -> None:
    from noesis.cli.content.help import build_help_screen
    from typer.main import get_command as get_typer_command

    options = GlobalOptions()
    ctx = build_context(options, port_specs=[])
    if command:
        # Build a minimal help text without invoking Click directly.
        group = get_typer_command(app)
        cmd = group.commands.get(command) if group else None
        if cmd is None:
            renderer = _select_renderer(ctx, json_output=False, quiet=False, force_rich=False)
            renderer.print_help(build_help_screen(ctx.version))
            renderer.echo(f"Unknown command: {command}")
            raise typer.Exit(code=1)

        lines: list[str] = [f"usage: noesis {command}"]
        for param in getattr(cmd, "params", []):
            opts = getattr(param, "opts", None) or []
            if opts:
                opt_str = ", ".join(opts)
                help_text = getattr(param, "help", "") or getattr(param, "description", "") or ""
                lines.append(f"{opt_str}  {help_text}".rstrip())
        sys.stdout.write("\n".join(lines) + "\n")
        return
    renderer = _select_renderer(ctx, json_output=False, quiet=False, force_rich=False)
    renderer.print_help(build_help_screen(ctx.version))


def main(argv: Optional[list[str]] = None) -> int:
    global _LAST_ARGV
    _LAST_ARGV = list(argv) if argv is not None else None
    if argv:
        args = list(argv)
        if args and args[0] == "run" and "--json" in args:
            raw_version = None
            for token in args:
                if token.startswith("--cli-version="):
                    raw_version = token.split("=", 1)[1]
                    break
            if raw_version is None and "--cli-version" in args:
                idx = args.index("--cli-version")
                if idx + 1 < len(args):
                    raw_version = args[idx + 1]
                else:
                    sys.stderr.write("invalid cli version (expected cli/MAJOR.MINOR)\n")
                    return 2
            if raw_version is not None:
                _version, error_code, version_error = _normalize_cli_version(raw_version)
                if version_error:
                    sys.stderr.write(f"{version_error}\n")
                    return error_code or 3
    try:
        result = app(standalone_mode=False, prog_name="noesis", args=argv)
        if result is not None:
            return result
    except typer.Exit as exc:
        return exc.exit_code
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())
