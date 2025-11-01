from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer


class NewCommand:
    name = "new"
    help = "Scaffold a starter flow or policy (experimental)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("kind", choices=("flow", "policy"), help="Artifact to scaffold")
        parser.add_argument("name", help="Name for the scaffold")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress message")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        message = (
            f"Scaffolding for '{args.kind} {args.name}' is coming soon. "
            "Create flows/ or policies manually for now."
        )
        if args.json:
            renderer.json({"status": "todo", "kind": args.kind, "name": args.name, "message": message})
        elif not args.quiet:
            renderer.echo(message)
        return 0


COMMAND = NewCommand()
