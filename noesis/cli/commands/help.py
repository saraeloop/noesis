"""Help command: noesis help [command]"""
from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer


class HelpCommand:
    name = "help"
    help = "Show help for Noēsis or a specific command"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("command", nargs="?", help="Command name to show help for")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        # Lazy import to avoid circular dependency
        from ..content.help import build_help_screen

        if args.command:
            from ..parser import build_command_parser

            command_parser = build_command_parser(args.command, argparse.RawTextHelpFormatter)
            if command_parser:
                renderer.print_command_help(command_parser.format_help(), title=f"noesis {args.command}")
                return 0
            renderer.echo(f"Unknown command: {args.command}")
        renderer.print_help(build_help_screen(ctx.version))
        return 0


COMMAND = HelpCommand()
