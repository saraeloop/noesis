from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

import argparse

import noesis as ns

from .context import GlobalOptions, build_context
from .errors import EXIT_ERROR, EXIT_USAGE, EXIT_VETO
from .render.plain import PlainRenderer
from .content.home import build_home_screen
from .content.help import build_help_screen
from .theme import build_theme_tokens


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

from .parser import build_command_parser, build_parser
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
    if options.json or options.quiet or os.environ.get("NO_COLOR"):
        return PlainRenderer(quiet=options.quiet)
    if not _HAS_RICH:
        return PlainRenderer(quiet=options.quiet)
    if not ctx.isatty and not options.force_rich:
        return PlainRenderer(quiet=options.quiet)
    theme_tokens = build_theme_tokens()
    console = Console(
        theme=Theme(theme_tokens.styles),
        force_terminal=options.force_rich,
        soft_wrap=True,
    )
    return RichRenderer(console, quiet=options.quiet)


def _argv_has_flag(argv: Sequence[str], *flags: str) -> bool:
    return any(token in flags for token in argv)


def _detect_help_target(argv: Sequence[str]) -> Optional[str]:
    if not _argv_has_flag(argv, "-h", "--help"):
        return None
    for token in argv:
        if token in {"-h", "--help"}:
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def _options_from_argv(argv: Sequence[str]) -> GlobalOptions:
    env_force_rich = _env_bool("NOESIS_FORCE_RICH")
    return GlobalOptions(
        json=_argv_has_flag(argv, "-j", "--json"),
        quiet=_argv_has_flag(argv, "-q", "--quiet"),
        force_rich=_argv_has_flag(argv, "--force-rich") or bool(env_force_rich),
    )


def _render_home(renderer, ctx) -> None:
    renderer.print_home(build_home_screen(ctx.version))


def _render_help(renderer, ctx, *, command_name: str | None = None) -> None:
    if command_name:
        formatter = argparse.RawTextHelpFormatter
        command = COMMANDS.get(command_name)
        if not command:
            renderer.print_help(build_help_screen(ctx.version))
            renderer.echo(f"Unknown command: {command_name}")
            return
        command_parser = build_command_parser(command_name, formatter)
        if command_parser:
            renderer.print_command_help(command_parser.format_help(), title=f"noesis {command_name}")
            return
    renderer.print_help(build_help_screen(ctx.version))


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    help_target = _detect_help_target(raw_argv)
    if help_target is not None:
        options = _options_from_argv(raw_argv)
        ctx = build_context(options, port_specs=[])
        renderer = _select_renderer(ctx, options)
        _render_help(renderer, ctx, command_name=help_target)
        return 0

    formatter = _choose_formatter()
    parser, _ = build_parser(formatter)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    env_compact = _env_bool("NOESIS_COMPACT")
    env_verbose = _env_bool("NOESIS_VERBOSE")
    env_debug = _env_bool("NOESIS_DEBUG")
    env_force_rich = _env_bool("NOESIS_FORCE_RICH")
    env_home = _env_bool("NOESIS_HOME")

    compact_arg = getattr(args, "compact", None)
    verbose_arg = getattr(args, "verbose", None)
    debug_arg = getattr(args, "debug", None)
    force_rich_arg = getattr(args, "force_rich", None)
    home_arg = getattr(args, "home", None)

    options = GlobalOptions(
        compact=compact_arg if compact_arg is not None else env_compact,
        verbose=bool(verbose_arg) or bool(env_verbose),
        debug=bool(debug_arg) or bool(env_debug),
        json=bool(getattr(args, "json", False)),
        quiet=bool(getattr(args, "quiet", False)),
        force_rich=bool(force_rich_arg) if force_rich_arg is not None else bool(env_force_rich),
    )
    options.normalize()
    if options.compact is None:
        options.compact = True

    port_specs = getattr(args, "port", []) or []
    ctx = build_context(options, port_specs)
    renderer = _select_renderer(ctx, options)

    command = getattr(args, "command_obj", None)
    home_requested = bool(home_arg) if home_arg is not None else bool(env_home)
    if home_requested and not (options.json or options.quiet):
        _render_home(renderer, ctx)
        return 0 if command is not None else EXIT_USAGE

    if command is None:
        _render_home(renderer, ctx)
        return 0

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
