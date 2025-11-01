from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer


class ValidatePortsCommand:
    name = "validate-ports"
    help = "Validate configured runtime ports"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress human output")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        ports = ctx.runtime_context.list_ports()
        if args.json:
            renderer.json({"ports": ports})
            return 0
        if not args.quiet:
            if not ports:
                renderer.echo("No ports registered.")
            else:
                for name, api in sorted(ports.items()):
                    renderer.echo(f"{name}: {api}")
        return 0


COMMAND = ValidatePortsCommand()
