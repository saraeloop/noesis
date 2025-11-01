from __future__ import annotations

import argparse
from typing import Dict, Iterable, List

from ..context import RuntimeContext
from ..render.base import OutputRenderer


class EventsCommand:
    name = "events"
    help = "Print or stream events for an episode"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("episode_id", help="Episode identifier")
        parser.add_argument(
            "--phase",
            help=(
                "Filter by phase "
                "(start|observe|interpret|plan|act|reflect|learn|intuition|direction|insight|reason|terminate|error)"
            ),
        )
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress banner")

    def run(self, args: argparse.Namespace, ctx: RuntimeContext, renderer: OutputRenderer) -> int:
        events: List[Dict[str, any]] = list(ctx.ns.events(args.episode_id, container=ctx.container))
        if args.phase:
            events = [e for e in events if e.get("phase") == args.phase]

        if args.json:
            for event in events:
                renderer.json(event)
            return 0

        if events and not args.quiet:
            renderer.echo(f"Episode: {args.episode_id}")
        if not events and not args.quiet:
            renderer.echo("No events matched.")
        renderer.print_events(events)
        return 0


COMMAND = EventsCommand()
