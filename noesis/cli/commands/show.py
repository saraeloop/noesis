from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer


class ShowCommand:
    name = "show"
    help = "Show a single episode summary"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("episode_id", help="Episode identifier")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Print id only")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        summary = ctx.ns.summary(args.episode_id, context=ctx.runtime_context)
        if args.json:
            renderer.json(summary)
            return 0
        if args.quiet:
            renderer.echo(summary.get("episode_id", ""))
            return 0
        renderer.print_summary(summary)
        return 0


COMMAND = ShowCommand()
