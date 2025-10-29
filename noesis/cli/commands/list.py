from __future__ import annotations

import argparse

from ..context import RuntimeContext
from ..render.base import OutputRenderer


class ListCommand:
    name = "list"
    help = "List recent episodes"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--limit", type=int, default=20, help="Number of episodes to show (default: 20)")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Show episode ids only")

    def run(self, args: argparse.Namespace, ctx: RuntimeContext, renderer: OutputRenderer) -> int:
        rows = ctx.ns.list_runs(limit=args.limit)
        if args.json:
            renderer.json(rows)
            return 0
        renderer.print_list(rows, quiet=args.quiet)
        return 0


COMMAND = ListCommand()
