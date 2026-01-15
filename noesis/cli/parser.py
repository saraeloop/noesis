from __future__ import annotations

import argparse
import noesis as ns

from .registry import register_commands


def build_global_parser() -> argparse.ArgumentParser:
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("--compact", action="store_true", default=None, help="Compact output (summary only)")
    global_parser.add_argument("--verbose", action="store_true", default=None, help="Verbose output (detailed reasoning)")
    global_parser.add_argument("--debug", action="store_true", default=None, help="Debug mode (trace internals)")
    global_parser.add_argument(
        "--force-rich",
        action="store_true",
        default=None,
        help="Force Rich output even when stdout is not a TTY",
    )
    global_parser.add_argument(
        "--port",
        action="append",
        default=[],
        metavar="NAME=SPEC",
        help="Register a runtime port (e.g. memory=acme.memory:FaissMemory(index_path='./mem'))",
    )
    global_parser.add_argument(
        "--home",
        action="store_true",
        default=None,
        help="Show the Noēsis home screen (useful for demos)",
    )
    return global_parser


def build_parser(formatter_class: type[argparse.HelpFormatter]) -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    global_parser = build_global_parser()
    quick = "Quick start:\n  noesis run \"Summarize this repo\"\n  noesis solve react \"Weekly plan\"\n  noesis insight <episode_id> -j"
    cheat = (
        "Cheat sheet:\n"
        "  run       baseline episode\n"
        "  solve     adapter episode\n"
        "  list      recent runs\n"
        "  ps        compact processes table\n"
        "  show      episode summary\n"
        "  view      timeline + governance report\n"
        "  events    stream events\n"
        "  insight   computed metrics snapshot\n"
        "  artifacts verify <episode>  verify manifest integrity\n"
        "  migrate   update deprecated shims\n"
        "  version   CLI + core versions\n"
        "  new       experimental scaffolder"
    )
    version_line = f"Noesis {getattr(ns, '__version__', 'unknown')}"
    parser = argparse.ArgumentParser(
        prog="noesis",
        description="✨ Noēsis CLI ✨\nrun, steer, and observe agentic workflows",
        formatter_class=formatter_class,
        parents=[global_parser],
        epilog=f"{quick}\n\n{cheat}\n\n{version_line}"
    )
    sub = parser.add_subparsers(dest="command")
    register_commands(sub, parents=[global_parser], formatter_class=formatter_class)
    return parser, global_parser


def build_command_parser(
    command_name: str,
    formatter_class: type[argparse.HelpFormatter],
) -> argparse.ArgumentParser | None:
    global_parser = build_global_parser()
    from .registry import COMMANDS

    cmd = COMMANDS.get(command_name)
    if not cmd:
        return None
    parser = argparse.ArgumentParser(
        prog=f"noesis {command_name}",
        formatter_class=formatter_class,
        parents=[global_parser],
    )
    cmd.add_arguments(parser)
    return parser
