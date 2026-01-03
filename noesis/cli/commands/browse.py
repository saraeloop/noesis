"""Browse command: interactive episode browser TUI."""
from __future__ import annotations

import argparse
from typing import Any

from ..context import CLIContext
from ..render.base import OutputRenderer


class BrowseCommand:
    """Interactive episode browser using Textual TUI."""

    name = "browse"
    help = "Interactive episode browser (TUI)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-n", "--limit",
            type=int,
            default=50,
            help="Maximum episodes to load (default: 50)",
        )

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        """Launch the interactive browser."""
        try:
            from ..tui.browse import run_browse
        except ImportError as e:
            renderer.echo(f"Textual not available: {e}")
            renderer.echo("Install with: pip install textual")
            return 1

        # Fetch episodes
        episodes = self._fetch_episodes(ctx, limit=args.limit)

        if not episodes:
            renderer.echo("No episodes found. Run some tasks first!")
            renderer.echo("  $ noesis run 'your task here'")
            return 0

        # Launch the TUI
        runs_dir = ctx.config_snapshot.runs_dir
        run_browse(episodes, runs_dir=runs_dir)

        return 0

    def _fetch_episodes(self, ctx: CLIContext, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent episodes."""
        try:
            rows = ctx.ns.list_runs(limit=limit, context=ctx.runtime_context)
            return list(rows) if rows else []
        except Exception:  # noqa: BLE001
            return []


COMMAND = BrowseCommand()
