from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

import argparse

import noesis as ns

from .context import GlobalOptions, build_context
from .errors import EXIT_ERROR, EXIT_USAGE, EXIT_VETO
from .render.plain import PlainRenderer


try:
    from rich.console import Console
    from rich.theme import Theme
    from .render.richy import RichRenderer
    _HAS_RICH = True
except Exception:  # noqa: BLE001
    Console = None  # type: ignore[assignment]
    Theme = None  # type: ignore[assignment]
    RichRenderer = None  # type: ignore[assignment]
    _HAS_RICH = False

from .parser import build_parser
from .registry import COMMANDS


def _env_bool(name: str) -> Optional[bool]:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _choose_formatter():
    if _HAS_RICH:
        try:
            from rich_argparse import RichHelpFormatter
        except ImportError:
            return argparse.RawTextHelpFormatter
        return RichHelpFormatter
    return argparse.RawTextHelpFormatter


def _select_renderer(ctx, options: GlobalOptions):
    if options.json or options.quiet or not ctx.isatty or not _HAS_RICH or os.environ.get("NO_COLOR"):
        return PlainRenderer(quiet=options.quiet)
    console = Console(
        theme=Theme(
            {
                "title": "bold magenta",
                "ok": "green",
                "warn": "yellow",
                "err": "bold red",
                "muted": "dim",
                "key": "cyan",
                "val": "white",
                "phase.start": "cyan",
                "phase.intuition": "magenta",
                "phase.observe": "bright_black",
                "phase.interpret": "bright_blue",
                "phase.plan": "bright_cyan",
                "phase.direction": "blue",
                "phase.insight": "green",
                "phase.reason": "bright_black",
                "phase.act": "white",
                "phase.reflect": "green",
                "phase.learn": "cyan",
                "phase.terminate": "yellow",
                "phase.error": "bold red",
            }
        ),
        soft_wrap=True,
    )
    return RichRenderer(console, quiet=options.quiet)


def main(argv: Optional[Sequence[str]] = None) -> int:
    formatter = _choose_formatter()
    parser, _ = build_parser(formatter)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    if not getattr(args, "command_obj", None):
        parser.print_help()
        return EXIT_USAGE

    env_compact = _env_bool("NOESIS_COMPACT")
    env_verbose = _env_bool("NOESIS_VERBOSE")
    env_debug = _env_bool("NOESIS_DEBUG")

    compact_arg = getattr(args, "compact", None)
    verbose_arg = getattr(args, "verbose", None)
    debug_arg = getattr(args, "debug", None)

    options = GlobalOptions(
        compact=compact_arg if compact_arg is not None else env_compact,
        verbose=bool(verbose_arg) or bool(env_verbose),
        debug=bool(debug_arg) or bool(env_debug),
        json=bool(getattr(args, "json", False)),
        quiet=bool(getattr(args, "quiet", False)),
    )
    options.normalize()
    if options.compact is None:
        options.compact = True

    port_specs = getattr(args, "port", []) or []
    ctx = build_context(options, port_specs)
    renderer = _select_renderer(ctx, options)

    command = args.command_obj
    provider = ns.session_provider()
    try:
        with provider.use(ctx.session):
            return command.run(args, ctx, renderer)
    except ns.NoesisVeto as veto:  # type: ignore[name-defined]
        print(veto.advice or "Vetoed by policy", file=sys.stderr)
        return EXIT_VETO
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as err:  # noqa: BLE001
        print(f"error: {err}", file=sys.stderr)
        return EXIT_ERROR
