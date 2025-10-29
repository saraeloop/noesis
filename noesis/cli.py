"""
Noēsis command-line interface (CLI) — run, steer, and inspect episodes.

Design tenets
-------------
- Command nouns, verb flags: `noesis run`, `noesis solve`, `noesis events`, etc.
- Human-friendly output by default, JSON on demand (`-j/--json`).
- Shared ergonomics: quiet mode (`-q/--quiet`), tag injection, stdin helpers.
- Perfect help screens: concise, aligned, copy/paste ready.
- Deterministic exit codes for CI (usage=2, veto=3, error=1).
- Optional color/UI: uses `rich` if available; plain output otherwise.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import sys
from typing import Any, Callable, Dict, Iterable, Optional, Sequence

import noesis as ns
from noesis import config as _cfg

# Rich UI helpers
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.theme import Theme
    from rich_argparse import RichHelpFormatter
    _HAS_RICH = True
except Exception:  # noqa: BLE001
    Console = Panel = Table = Text = Syntax = Theme = None  # type: ignore[assignment]
    RichHelpFormatter = argparse.RawTextHelpFormatter  # type: ignore[assignment]
    _HAS_RICH = False


def _console() -> "Console":
    """
    Build a themed console. Honors NO_COLOR and TTY automatically via rich.
    """
    if not _HAS_RICH:
        raise RuntimeError("console() requested without Rich installed")
    theme = Theme(
        {
            "title": "bold magenta",
            "ok": "green",
            "warn": "yellow",
            "err": "bold red",
            "muted": "dim",
            "key": "cyan",
            "val": "white",
            "phase.start": "cyan",
            "phase.intuition": "magenta",
            "phase.direction": "blue",
            "phase.insight": "green",
            "phase.reason": "bright_black",
            "phase.act": "white",
            "phase.terminate": "yellow",
            "phase.error": "bold red",
        }
    )
    return Console(theme=theme, soft_wrap=True)


def _print_pretty_json(data: Any) -> None:
    """
    Human-friendly JSON pretty printer with syntax highlighting if Rich present.
    Do not use for machine `-j` paths.
    """
    if not _HAS_RICH:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    con = _console()
    src = json.dumps(data, indent=2, ensure_ascii=False)
    con.print(Syntax(src, "json", word_wrap=True))


# Policy alias registry (built-ins merged with config at runtime)

_BUILTIN_POLICY_ALIASES: Dict[str, str] = {
    "guardrails": "noesis.examples.direction_demo.policy:GuardrailsPolicy",
}


def _env_flag(name: str) -> bool:
    val = os.environ.get(name)
    if val is None:
        return False
    return val.strip().lower() not in {"0", "false", "off", "no", ""}

# Global flags
_GLOBAL = argparse.ArgumentParser(add_help=False)
_GLOBAL.add_argument("--compact", action="store_true", help="Compact output (summary only)")
_GLOBAL.add_argument("--verbose", action="store_true", help="Verbose output (detailed reasoning)")
_GLOBAL.add_argument("--debug", action="store_true", help="Debug mode (trace internals)")


def _policy_aliases() -> Dict[str, str]:
    merged = dict(_BUILTIN_POLICY_ALIASES)
    cfg_aliases = _cfg.get().get("policy_aliases") or {}
    merged.update(cfg_aliases)
    return merged


def _resolve_policy_spec(spec: Optional[str]) -> Any:
    """
    Resolve a policy spec with modern ergonomics:
      - None → True (default intuition on)
      - "on"/"true"/"yes" → True
      - "off"/"false"/"no" → False
      - alias → lookup via config/built-ins
      - "module:Class" or "pkg.Class" → import dynamically
    """
    if spec is None:
        return True
    s = spec.strip()
    lowered = s.lower()
    if lowered in {"on", "true", "yes"}:
        return True
    if lowered in {"off", "false", "no"}:
        return False

    target = _policy_aliases().get(s, s)

    if ":" in target:
        module_name, class_name = target.split(":", 1)
    else:
        parts = target.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Policy spec must be an alias ('guardrails') or 'module:Class'/'pkg.Class', got {spec!r}"
            )
        module_name, class_name = parts

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ValueError(f"Cannot import module '{module_name}' for policy alias '{spec}': {exc}") from exc

    try:
        policy_cls: Callable[..., Any] = getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(f"Module '{module_name}' has no class '{class_name}'") from exc

    return policy_cls()


# Shared helpers

def _parse_tags(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for --tags: {raw}") from exc
    if not isinstance(value, dict):
        raise ValueError("--tags must decode to a JSON object")
    return value


def _read_task(task_arg: Optional[str], *, use_stdin: bool) -> str:
    if use_stdin or task_arg == "-":
        return sys.stdin.read()
    if not task_arg:
        raise ValueError("Task prompt required (pass --stdin or '-' to read from STDIN)")
    return task_arg


def _apply_dir_min(value: Optional[float]) -> None:
    if value is not None:
        ns.set(direction_min_confidence=float(value))


def _determine_intuition(policy_spec: Optional[str], no_intuition: bool) -> Any:
    if no_intuition:
        return False
    return _resolve_policy_spec(policy_spec)


def _is_verbose(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "verbose", False) or getattr(args, "debug", False))


def _is_compact(args: argparse.Namespace) -> bool:
    if _is_verbose(args):
        return False
    return bool(getattr(args, "compact", False))


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _print_list(rows: Iterable[Dict[str, Any]], *, quiet: bool) -> None:
    if quiet:
        for row in rows:
            eid = row.get("episode_id")
            if eid:
                print(eid)
        return

    if not _HAS_RICH:
        header = f"{'STARTED_AT':>25}  {'EPISODE_ID':28}  TASK"
        print(header)
        print("-" * len(header))
        for r in rows:
            started = (r.get("started_at") or "")[:25]
            episode_id = (r.get("episode_id") or "")[:28]
            task = r.get("task") or ""
            print(f"{started:>25}  {episode_id:28}  {task}")
        return

    con = _console()
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
    table.add_column("TASK", style="val", overflow="fold")
    for r in rows:
        started = (r.get("started_at") or "")[:25]
        eid = (r.get("episode_id") or "")[:28]
        task = r.get("task") or ""
        table.add_row(started, eid, task)
    con.print(table)


def _print_summary(summary: Dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        print(summary.get("episode_id", ""))
        return

    if not _HAS_RICH:
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
        last_diff = direction_flags.get("last_diff") or []
        diff_text = ", ".join(last_diff) if last_diff else "—"
        print(f"  policy    : {policy}")
        print(f"  threshold : {direction_flags.get('threshold')}")
        print(f"  applied   : {direction_flags.get('applied')}  vetoed: {direction_flags.get('vetoed')}")
        print(f"  last_diff : {diff_text}")

        print("\nMetrics (highlights)")
        highlights = (
            "direction_events",
            "direction_applied",
            "direction_vetoed",
            "veto_rate",
            "top_reasons",
            "steps",
        )
        for key in highlights:
            print(f"  {key:18}: {metrics.get(key)}")
        return

    con = _console()
    flags = summary.get("flags", {}) or {}
    df = flags.get("direction", {}) or {}
    metrics = summary.get("metrics", {}) or {}

    header = Text(f"Episode {summary.get('episode_id','')}", style="title")

    body = Table.grid(padding=(0, 1))
    body.add_row(Text("task", style="key"), Text(summary.get("task", ""), style="val"))
    body.add_row(Text("started", style="key"), Text(summary.get("started_at", ""), style="val"))
    dur_val = "—" if summary.get("duration_sec") is None else f"{summary.get('duration_sec')}s"
    body.add_row(Text("duration", style="key"), Text(dur_val, style="val"))

    flags_tbl = Table.grid(padding=(0, 1))
    flags_tbl.add_row(Text("intuition", style="key"), Text(f"{flags.get('intuition')} (mode={flags.get('mode')})", style="val"))
    if "using" in flags:
        flags_tbl.add_row(Text("using", style="key"), Text(flags["using"], style="val"))

    dir_tbl = Table.grid(padding=(0, 1))
    dir_tbl.add_row(Text("policy", style="key"), Text(df.get("policy", "—"), style="val"))
    dir_tbl.add_row(Text("threshold", style="key"), Text(str(df.get("threshold")), style="val"))
    dir_tbl.add_row(Text("applied", style="key"), Text(str(df.get("applied")), style="ok"))
    dir_tbl.add_row(Text("vetoed", style="key"), Text(str(df.get("vetoed")), style="err"))
    last_diff = ", ".join(df.get("last_diff") or []) or "—"
    dir_tbl.add_row(Text("last_diff", style="key"), Text(last_diff, style="val"))

    m_tbl = Table.grid(padding=(0, 1))
    for k in ("direction_events", "direction_applied", "direction_vetoed", "veto_rate", "top_reasons", "steps"):
        m_tbl.add_row(Text(k, style="key"), Text(str(metrics.get(k)), style="val"))

    con.print(Panel(body, title=header, border_style="title"))
    con.print(Panel(flags_tbl, title="[title]Flags[/]"))
    con.print(Panel(dir_tbl, title="[title]Direction[/]"))
    con.print(Panel(m_tbl, title="[title]Metrics[/]"))


def _print_event(event: Dict[str, Any]) -> None:
    if not _HAS_RICH:
        timestamp = event.get("timestamp", "")
        phase = event.get("phase", "")
        payload = event.get("payload", {})
        extras = []
        for k in ("reason", "status"):
            v = payload.get(k)
            if v is not None:
                extras.append(f"{k}={v}")
        diff = payload.get("diff")
        if diff:
            extras.append(f"diff={diff}")
        print(f"[{timestamp}] {phase:<10} {'  '.join(extras)}".rstrip())
        return

    con = _console()
    phase = event.get("phase", "")
    style = f"phase.{phase}" if f"phase.{phase}" in con.theme.styles else "val"
    timestamp = Text(event.get("timestamp", ""), style="muted")
    payload = event.get("payload", {}) or {}
    extras = []
    for k in ("reason", "status"):
        v = payload.get(k)
        if v is not None:
            extras.append(f"{k}={v}")
    diff = payload.get("diff")
    if diff:
        extras.append(f"diff={diff}")
    line = Text.assemble(
        "[", timestamp, "] ",
        Text(f"{phase:<10}", style=style), " ",
        Text("  ".join(extras), style="val"),
    )
    con.print(line)


def _iter_events(episode_id: str, phase: Optional[str]) -> Iterable[Dict[str, Any]]:
    events = ns.events(episode_id)
    for event in events:
        if phase and event.get("phase") != phase:
            continue
        yield event


def _adapter_statuses() -> Sequence[str]:
    adapters = [
        ("langgraph", "noesis.adapters.langgraph", "on"),
        ("crewai", "noesis.adapters.crewai", "exp"),
        ("assistants", "noesis.adapters.assistant", "exp"),
    ]
    statuses = []
    for name, module, label in adapters:
        available = importlib.util.find_spec(module) is not None
        state = "on" if available else "off"
        if label == "exp":
            state = "exp" if available else "missing"
        statuses.append(f"{name}@{state}")
    return statuses



# Commands

def cmd_run(args: argparse.Namespace) -> int:
    _apply_dir_min(args.dir_min)
    task = _read_task(args.task, use_stdin=args.stdin)
    tags = _parse_tags(args.tags)

    episode_id = ns.run(
        task=task,
        seed=args.seed,
        intuition=_determine_intuition(args.policy, args.no_intuition),
        tags=tags,
    )

    if args.json:
        _print_json({"episode_id": episode_id})
    elif args.quiet:
        print(episode_id)
    else:
        print(f"Episode: {episode_id}")
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    _apply_dir_min(args.dir_min)
    task = _read_task(args.task, use_stdin=args.stdin)
    tags = _parse_tags(args.tags)

    episode_id = ns.solve(
        task=task,
        using=args.adapter,
        seed=args.seed,
        intuition=_determine_intuition(args.policy, args.no_intuition),
        tags=tags,
    )

    if args.json:
        _print_json({"episode_id": episode_id})
    elif args.quiet:
        print(episode_id)
    else:
        print(f"Episode: {episode_id}")
    return 0


def cmd_list_runs(args: argparse.Namespace) -> int:
    rows = ns.list_runs(limit=args.limit)
    if args.json:
        _print_json(rows)
    else:
        _print_list(rows, quiet=args.quiet)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    summary = ns.summary(args.episode_id)
    if args.json:
        _print_json(summary)
    else:
        _print_summary(summary, quiet=args.quiet)
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    events = list(_iter_events(args.episode_id, args.phase))
    if args.json:
        for event in events:
            _print_json(event)
    else:
        if events and not args.quiet:
            if _HAS_RICH:
                _console().print(Text(f"Episode: {args.episode_id}", style="title"))
            else:
                print(f"Episode: {args.episode_id}")
        if not events and not args.quiet:
            print("No events matched.")
        for event in events:
            _print_event(event)
    return 0


def cmd_insight(args: argparse.Namespace) -> int:
    setattr(args, "phase", "insight")
    return cmd_events(args)


def cmd_demo(args: argparse.Namespace) -> int:
    if args.which == "direction":
        mod = importlib.import_module("noesis.examples.direction_demo.direction_demo")
        mod.main()
        return 0
    if args.which == "city":
        mod = importlib.import_module("noesis.examples.city_analysis.city_analysis")
        if hasattr(mod, "main"):
            mod.main()
        return 0
    print("Available demos: direction, city", file=sys.stderr)
    return 2


def cmd_new(args: argparse.Namespace) -> int:
    kind = args.kind
    name = args.name
    message = (
        f"Scaffolding for '{kind} {name}' is coming soon. "
        "Create flows/ or policies manually for now."
    )
    if args.json:
        _print_json({"status": "todo", "kind": kind, "name": name, "message": message})
    elif not args.quiet:
        print(message)
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    adapter_list = list(_adapter_statuses())
    version_string = f"noesis {ns.__version__} (core {ns.__version__}, adapters: {', '.join(adapter_list)})"
    if args.json:
        _print_json(
            {
                "noesis": ns.__version__,
                "core": ns.__version__,
                "adapters": adapter_list,
            }
        )
    else:
        print(version_string)
    return 0



# Parser

def _add_common_flags(parser: argparse.ArgumentParser, *, include_json: bool = True) -> None:
    if include_json:
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress human-friendly output")


def _build_description() -> str:
    if _HAS_RICH:
        return "✨ Noēsis CLI ✨\nrun, steer, and observe agentic workflows"
    return "Noēsis CLI — run, steer, and observe agentic workflows"


def build_parser() -> argparse.ArgumentParser:
    if _HAS_RICH:
        quick = "[bold]Quick start[/]\n  noesis run \"Summarize this repo\"\n  noesis solve react \"Weekly plan\"\n  noesis insight <ep> -j"
        cheat = "[bold]Cheat sheet[/]\n  run       baseline episode\n  solve     adapter episode\n  list      recent runs\n  show      episode summary\n  events    stream events\n  insight   computed metrics snapshot\n  demo      showcase (use --verbose)"
        version_line = f"[muted]noesis {ns.__version__}[/]"
    else:
        quick = "Quick start:\n  noesis run \"Summarize this repo\"\n  noesis solve react \"Weekly plan\"\n  noesis insight <episode_id> -j"
        cheat = "Cheat sheet:\n  run       baseline episode\n  solve     adapter episode\n  list      recent runs\n  show      episode summary\n  events    stream events\n  insight   computed metrics snapshot\n  demo      showcase (use --verbose)"
        version_line = f"noesis {ns.__version__}"

    epilog = f"{quick}\n\n{cheat}\n\n{version_line}"

    parser = argparse.ArgumentParser(
        prog="noesis",
        description=_build_description(),
        epilog=epilog,
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser(
        "run",
        help="Run a baseline episode (no adapter)",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    run_p.add_argument("task", nargs="?", help='Task prompt (use "-" or --stdin for STDIN)')
    run_p.add_argument("-s", "--seed", type=int, default=0, help="Seed (default: 0)")
    run_p.add_argument("-P", "--policy", help="Policy alias or module:Class (default: on)")
    run_p.add_argument("--tags", help="JSON object of tags to attach to the episode")
    run_p.add_argument("-y", "--yes", action="store_true", help="Assume yes for interactive prompts")
    run_p.add_argument("--dir-min", type=float, help="Direction min confidence override")
    run_p.add_argument("--stdin", action="store_true", help="Read task prompt from STDIN")
    run_p.add_argument("--no-intuition", action="store_true", help="Disable intuition entirely")
    _add_common_flags(run_p)
    run_p.set_defaults(func=cmd_run)

    # solve
    solve_p = sub.add_parser(
        "solve",
        help="Run an episode using a specific adapter/flow",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    solve_p.add_argument("adapter", help="Adapter name or import path")
    solve_p.add_argument("task", nargs="?", help='Task prompt (use "-" or --stdin for STDIN)')
    solve_p.add_argument("-s", "--seed", type=int, default=0, help="Seed (default: 0)")
    solve_p.add_argument("-P", "--policy", help="Policy alias or module:Class (default: on)")
    solve_p.add_argument("--tags", help="JSON object of tags to attach to the episode")
    solve_p.add_argument("--dir-min", type=float, help="Direction min confidence override")
    solve_p.add_argument("--stdin", action="store_true", help="Read task prompt from STDIN")
    solve_p.add_argument("--no-intuition", action="store_true", help="Disable intuition entirely")
    _add_common_flags(solve_p)
    solve_p.set_defaults(func=cmd_solve)

    # list
    list_p = sub.add_parser(
        "list",
        help="List recent episodes",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    list_p.add_argument("--limit", type=int, default=20, help="Number of episodes to show (default: 20)")
    _add_common_flags(list_p)
    list_p.set_defaults(func=cmd_list_runs)

    # show
    show_p = sub.add_parser(
        "show",
        help="Show a single episode summary",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    show_p.add_argument("episode_id", help="Episode identifier")
    _add_common_flags(show_p)
    show_p.set_defaults(func=cmd_show)

    # events
    events_p = sub.add_parser(
        "events",
        help="Print or stream events for an episode",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    events_p.add_argument("episode_id", help="Episode identifier")
    events_p.add_argument(
        "--phase",
        help="Filter by phase (start|intuition|direction|insight|reason|act|terminate|error)",
    )
    _add_common_flags(events_p)
    events_p.set_defaults(func=cmd_events)

    # demo
    demo_p = sub.add_parser(
        "demo",
        help="Run polished built-in demos",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    demo_p.add_argument("which", nargs="?", default="direction", help="Demo to run (direction | city)")
    demo_p.add_argument("--stress", action="store_true", help="Include stress tests (implied by --debug)")
    demo_p.set_defaults(func=cmd_demo)

    # new (experimental stub)
    new_p = sub.add_parser(
        "new",
        help="Scaffold a starter flow or policy (experimental)",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    new_p.add_argument("kind", choices=("flow", "policy"), help="Artifact to scaffold")
    new_p.add_argument("name", help="Name for the scaffold")
    _add_common_flags(new_p)
    new_p.set_defaults(func=cmd_new)

    # version
    version_p = sub.add_parser(
        "version",
        help="Print CLI and core versions",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    _add_common_flags(version_p)
    version_p.set_defaults(func=cmd_version)

    # insight (syntactic sugar)
    insight_p = sub.add_parser(
        "insight",
        help="Show computed insight metrics for an episode",
        formatter_class=(RichHelpFormatter if _HAS_RICH else argparse.RawTextHelpFormatter),
        parents=[_GLOBAL],
    )
    insight_p.add_argument("episode_id", help="Episode identifier")
    _add_common_flags(insight_p)
    insight_p.set_defaults(func=cmd_insight)

    return parser



# Entrypoint

def _env_bool(name: str, fallback: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # Preserve argparse exit codes (e.g., -h)
        return exc.code

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    env_debug = _env_bool("NOESIS_DEBUG")
    env_verbose = _env_bool("NOESIS_VERBOSE")
    env_compact = _env_bool("NOESIS_COMPACT")

    args.debug = bool(getattr(args, "debug", None))
    args.verbose = bool(getattr(args, "verbose", None))
    args.compact = bool(getattr(args, "compact", None))

    if args.debug is None:
        args.debug = env_debug
    if args.verbose is None:
        args.verbose = env_verbose
    if args.compact is None:
        args.compact = env_compact

    if args.debug:
        args.verbose = True
    if args.verbose:
        args.compact = False

    try:
        return args.func(args)
    except ns.NoesisVeto as veto:
        # Keep veto distinct for CI consumption
        print(veto.advice or "Vetoed by policy", file=sys.stderr)
        return 3
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # noqa: BLE001
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
