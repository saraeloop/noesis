from __future__ import annotations

import argparse
import noesis as ns

from .registry import register_commands


def _build_global_parser() -> argparse.ArgumentParser:
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("--compact", action="store_true", default=None, help="Compact output (summary only)")
    global_parser.add_argument("--verbose", action="store_true", default=None, help="Verbose output (detailed reasoning)")
    global_parser.add_argument("--debug", action="store_true", default=None, help="Debug mode (trace internals)")
    return global_parser


def build_parser(formatter_class: type[argparse.HelpFormatter]) -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    global_parser = _build_global_parser()
    quick = "Quick start:\n  noesis run \"Summarize this repo\"\n  noesis solve react \"Weekly plan\"\n  noesis insight <episode_id> -j"
    cheat = "Cheat sheet:\n  run       baseline episode\n  solve     adapter episode\n  list      recent runs\n  show      episode summary\n  events    stream events\n  insight   computed metrics snapshot\n  version   CLI + core versions\n  new       experimental scaffolder"
    version_line = f"noesis {getattr(ns, '__version__', 'unknown')}"
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
