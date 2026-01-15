from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..utils import apply_dir_min, parse_tags, read_task, resolve_policy_spec
from ..verification_input import compile_verify_input
from ..view_models import build_execution_map_from_summary, build_verification_section


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
        parser.add_argument("--workspace", help="Workspace root for verification snapshots")
        parser.add_argument("--process", help="Process label for grouping runs")
        parser.add_argument("--verify-file", help="JSON file of verification specs")
        parser.add_argument("--verify-file-exists", action="append", help="Require a file to exist (repeatable)")
        parser.add_argument(
            "--verify-file-contains",
            action="append",
            help="Require a file to contain text (repeatable; pair with --text)",
        )
        parser.add_argument(
            "--text",
            action="append",
            help="Text for --verify-file-contains (repeatable, order matters)",
        )
        parser.add_argument(
            "--verify-only-modified",
            action="append",
            help="Allow modifications only within the given path (repeatable)",
        )
        parser.add_argument(
            "--verify-no-modifications",
            action="store_true",
            help="Require no workspace modifications",
        )
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
        workspace = Path(args.workspace).expanduser() if args.workspace else None
        process = args.process
        verify = compile_verify_input(
            verify_file=args.verify_file,
            verify_file_exists=args.verify_file_exists,
            verify_file_contains=args.verify_file_contains,
            verify_texts=args.text,
            verify_only_modified=args.verify_only_modified,
            verify_no_modifications=bool(args.verify_no_modifications),
        )

        episode_id = ctx.ns.solve(
            task=task,
            using=args.adapter,
            seed=args.seed,
            intuition=intuition,
            tags=tags,
            context=ctx.runtime_context,
            workspace=workspace,
            process=process,
            verify=verify,
        )

        if getattr(args, "json", False):
            renderer.json({"episode_id": episode_id})
        elif getattr(args, "quiet", False):
            renderer.echo(episode_id)
        else:
            renderer.echo(f"Episode: {episode_id}")
            renderer.echo(f"Task: {task}")
            summary = ctx.ns.summary.read(episode_id, context=ctx.runtime_context)
            execution_map = build_execution_map_from_summary(summary)
            renderer.print_execution_map(execution_map, compact=True)
            if workspace is not None:
                renderer.echo(f"Workspace: {workspace.resolve()}")
            verification = build_verification_section(summary)
            diff = verification.workspace_diff
            if diff is not None:
                renderer.echo(
                    "Diff: "
                    f"+{len(diff.added)} ~{len(diff.modified)} -{len(diff.deleted)}"
                )
            renderer.echo(f"-> noesis view {episode_id}")
        return 0


COMMAND = SolveCommand()
