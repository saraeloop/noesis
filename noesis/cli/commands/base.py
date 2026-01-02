"""Command protocol and base types.

The canonical Command protocol is defined in noesis.cli.registry.
This module re-exports it for backward compatibility.
"""
from __future__ import annotations

import argparse
from typing import Protocol

from ..context import CLIContext
from ..render.base import OutputRenderer


class Command(Protocol):
    """Protocol for CLI commands."""

    name: str
    help: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int: ...
