from __future__ import annotations

import argparse
from typing import Protocol

from ..context import RuntimeContext
from ..render.base import OutputRenderer


class Command(Protocol):
    name: str
    help: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace, ctx: RuntimeContext, renderer: OutputRenderer) -> int: ...
