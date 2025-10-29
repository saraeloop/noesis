from __future__ import annotations

import argparse

from ..context import RuntimeContext
from ..render.base import OutputRenderer
from .events import EventsCommand


class InsightCommand:
    name = "insight"
    help = "Show computed insight metrics for an episode"

    def __init__(self) -> None:
        self._events = EventsCommand()

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("episode_id", help="Episode identifier")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress banner")

    def run(self, args: argparse.Namespace, ctx: RuntimeContext, renderer: OutputRenderer) -> int:
        setattr(args, "phase", "insight")
        return self._events.run(args, ctx, renderer)


COMMAND = InsightCommand()
