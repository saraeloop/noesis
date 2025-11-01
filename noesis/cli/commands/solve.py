from __future__ import annotations

import argparse
from typing import Any

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..utils import apply_dir_min, parse_tags, read_task, resolve_policy_spec


class SolveCommand:
    name = "solve"
    help = "Run an episode using a specific adapter/flow"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("adapter", help="Adapter name or import path")
        parser.add_argument("task", nargs="?", help='Task prompt (use "-" or --stdin for STDIN)')
        parser.add_argument("-s", "--seed", type=int, default=0, help="Seed (default: 0)")
        parser.add_argument("-P", "--policy", help="Policy alias or module:Class (default: on)")
        parser.add_argument("--tags", help="JSON object of tags to attach to the episode")
        parser.add_argument("--dir-min", type=float, help="Direction min confidence override")
        parser.add_argument("--stdin", action="store_true", help="Read task prompt from STDIN")
        parser.add_argument("--no-intuition", action="store_true", help="Disable intuition entirely")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output (episode id)")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress human-friendly output")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        apply_dir_min(getattr(args, "dir_min", None))

        policy = resolve_policy_spec(args.policy)
        if args.no_intuition:
            intuition: Any = False
        elif args.policy is None:
            intuition = True
        elif isinstance(policy, bool):
            intuition = policy
        else:
            intuition = policy

        tags = parse_tags(args.tags)
        task = read_task(args.task, use_stdin=args.stdin)

        episode_id = ctx.ns.solve(
            task=task,
            using=args.adapter,
            seed=args.seed,
            intuition=intuition,
            tags=tags,
            context=ctx.runtime_context,
        )

        if getattr(args, "json", False):
            renderer.json({"episode_id": episode_id})
        elif getattr(args, "quiet", False):
            renderer.echo(episode_id)
        else:
            renderer.echo(f"Episode: {episode_id}")
        return 0


COMMAND = SolveCommand()
