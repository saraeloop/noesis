from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer


class VersionCommand:
    name = "version"
    help = "Print CLI and core versions"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        adapters = []
        for name, module, label in [
            ("langgraph", "noesis.adapters.langgraph", "on"),
            ("crewai", "noesis.adapters.crewai", "exp"),
            ("assistants", "noesis.adapters.assistant", "exp"),
        ]:
            available = importlib.util.find_spec(module) is not None
            state = "on" if available else "off"
            if label == "exp":
                state = "exp" if available else "missing"
            adapters.append(f"{name}@{state}")

        if args.json:
            renderer.json({
                "noesis": ctx.version,
                "core": ctx.version,
                "adapters": adapters,
            })
            return 0

        renderer.echo(f"noesis {ctx.version} (core {ctx.version}, adapters: {', '.join(adapters)})")
        return 0


import importlib.util


COMMAND = VersionCommand()
