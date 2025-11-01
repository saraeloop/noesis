from __future__ import annotations

import argparse
from typing import Dict

from .commands.base import Command
from .commands.run import COMMAND as RUN_COMMAND
from .commands.solve import COMMAND as SOLVE_COMMAND
from .commands.list import COMMAND as LIST_COMMAND
from .commands.show import COMMAND as SHOW_COMMAND
from .commands.events import COMMAND as EVENTS_COMMAND
from .commands.insight import COMMAND as INSIGHT_COMMAND
from .commands.version import COMMAND as VERSION_COMMAND
from .commands.new import COMMAND as NEW_COMMAND
from .commands.validate_ports import COMMAND as VALIDATE_COMMAND


COMMANDS: Dict[str, Command] = {cmd.name: cmd for cmd in (
    RUN_COMMAND,
    SOLVE_COMMAND,
    LIST_COMMAND,
    SHOW_COMMAND,
    EVENTS_COMMAND,
    INSIGHT_COMMAND,
    VERSION_COMMAND,
    NEW_COMMAND,
    VALIDATE_COMMAND,
)}


def register_commands(
    subparsers: argparse._SubParsersAction,
    *,
    parents: list[argparse.ArgumentParser],
    formatter_class: type[argparse.HelpFormatter],
) -> None:
    for command in COMMANDS.values():
        parser = subparsers.add_parser(
            command.name,
            help=command.help,
            formatter_class=formatter_class,
            parents=parents,
        )
        command.add_arguments(parser)
        parser.set_defaults(command_obj=command)
