"""Noēsis command-line interface (modern UX)."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any, Callable, Optional

import noesis as ns


# Policy alias registry 

_POLICY_ALIASES = {
    # demo alias → module:Class
    "guardrails": "noesis.examples.direction_demo.policy:GuardrailsPolicy",
    # add more as you publish examples
}


def _resolve_policy_spec(spec: Optional[str]) -> Any:
    """
    Resolve a policy spec with modern ergonomics:
      - None → True (enable default intuition)
      - "on"/"true"/"yes" → True
      - "off"/"false"/"no" → False
      - alias (e.g., "guardrails") → resolve via _POLICY_ALIASES
      - "module:Class" or "pkg.Class" → import dynamically
    """
    if spec is None:
        return True
    s = spec.strip().lower()
    if s in {"on", "true", "yes"}:
        return True
    if s in {"off", "false", "no"}:
        return False

    # alias?
    target = _POLICY_ALIASES.get(spec, spec)

    # module:Class or pkg.Class
    if ":" in target:
        module_name, class_name = target.split(":", 1)
    else:
        parts = target.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Policy must be an alias ('guardrails') or 'module:Class' / 'pkg.Class', got {spec!r}"
            )
        module_name, class_name = parts

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise ValueError(f"Cannot import module '{module_name}' for policy: {e}") from e

    try:
        policy_cls: Callable[..., Any] = getattr(module, class_name)
    except AttributeError as e:
        raise ValueError(f"Module '{module_name}' has no class '{class_name}'") from e

    return policy_cls()


def _parse_tags(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for --tags: {raw}") from exc
    if not isinstance(value, dict):
        raise ValueError("Tags JSON must decode to an object")
    return value


def _read_task(arg: str) -> str:
    """Allow '-' to mean 'read task from stdin'."""
    return sys.stdin.read() if arg == "-" else arg


# Commands

def cmd_run(args: argparse.Namespace) -> int:
    if args.dir_min is not None:
        ns.set(direction_min_confidence=float(args.dir_min))

    policy = _resolve_policy_spec(args.policy)
    intuition = False if args.no_intuition else policy
    tags = _parse_tags(args.tags)

    task = _read_task(args.task)
    ep = ns.run(task=task, seed=args.seed, intuition=intuition, tags=tags)
    print(ep)
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    if args.dir_min is not None:
        ns.set(direction_min_confidence=float(args.dir_min))

    policy = _resolve_policy_spec(args.policy)
    intuition = False if args.no_intuition else policy
    tags = _parse_tags(args.tags)

    task = _read_task(args.task)
    adapter = args.adapter  # positional, modern
    ep = ns.solve(task=task, using=adapter, seed=args.seed, intuition=intuition, tags=tags)
    print(ep)
    return 0


def cmd_list_runs(args: argparse.Namespace) -> int:
    rows = ns.list_runs(limit=args.limit)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        for r in rows:
            print(f"{r.get('started_at',''):25}  {r.get('episode_id','')}  {r.get('task','')}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    summ = ns.summary(args.episode_id)
    print(json.dumps(summ, indent=2, ensure_ascii=False))
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    evts = ns.events(args.episode_id)
    for e in evts:
        if args.phase and e.get("phase") != args.phase:
            continue
        if args.json:
            print(json.dumps(e, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(e, ensure_ascii=False))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run built-in demos: `noesis demo direction`."""
    if args.which == "direction":
        # Import main to avoid importing heavy deps at CLI load.
        mod = importlib.import_module("noesis.examples.direction_demo.direction_demo")
        mod.main()
        return 0
    elif args.which == "city":
        mod = importlib.import_module("noesis.examples.city_analysis.city_analysis")
        # that module runs on import-as-main, but expose a main() for consistency if you add it.
        return 0
    else:
        print("Available demos: direction, city", file=sys.stderr)
        return 2


# Parser (modern ergonomics)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="noesis", description="Noēsis CLI")
    sub = p.add_subparsers(dest="command")

    # noesis run "<task>"
    pr = sub.add_parser("run", help="Run a baseline episode (no adapter)")
    pr.add_argument("task", help='Task prompt or "-" for stdin')
    pr.add_argument("-s", "--seed", type=int, default=0)
    pr.add_argument("-P", "--policy", help="policy alias or module:Class (e.g., guardrails)")
    pr.add_argument("--no-intuition", action="store_true", help="disable intuition entirely")
    pr.add_argument("--tags", help="JSON object of tags")
    pr.add_argument("--dir-min", type=float, help="direction min confidence (default 0.5)")
    pr.set_defaults(func=cmd_run)

    # noesis solve react "<task>"
    ps = sub.add_parser("solve", help="Run with an adapter/flow")
    ps.add_argument("adapter", help="Adapter or flow id (e.g., react, guardrails)")
    ps.add_argument("task", help='Task prompt or "-" for stdin')
    ps.add_argument("-s", "--seed", type=int, default=0)
    ps.add_argument("-P", "--policy", help="policy alias or module:Class (e.g., guardrails)")
    ps.add_argument("--no-intuition", action="store_true")
    ps.add_argument("--tags", help="JSON object of tags")
    ps.add_argument("--dir-min", type=float, help="direction min confidence (default 0.5)")
    ps.set_defaults(func=cmd_solve)

    # noesis list
    pl = sub.add_parser("list", help="List recent runs")
    pl.add_argument("--limit", type=int, default=10)
    pl.add_argument("-j", "--json", action="store_true", help="JSON output")
    pl.set_defaults(func=cmd_list_runs)

    # noesis show <ep>
    psw = sub.add_parser("show", help="Show summary for an episode")
    psw.add_argument("episode_id")
    psw.set_defaults(func=cmd_show)

    # noesis events <ep> [--phase direction] [-j]
    pe = sub.add_parser("events", help="Print events for an episode")
    pe.add_argument("episode_id")
    pe.add_argument("--phase", help="Filter by phase (e.g., direction,intuition)")
    pe.add_argument("-j", "--json", action="store_true", help="pretty JSON output")
    pe.set_defaults(func=cmd_events)

    # noesis demo direction
    pd = sub.add_parser("demo", help="Run built-in demos")
    pd.add_argument("which", nargs="?", default="direction", help="demo name: direction | city")
    pd.set_defaults(func=cmd_demo)

    return p


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except ns.NoesisVeto as veto:
        # Keep veto distinct for CI consumption
        print(f"veto: {veto.advice}", file=sys.stderr)
        return 3
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())