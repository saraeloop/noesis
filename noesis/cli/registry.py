"""Unified command registry: single source of truth for CLI commands and metadata."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Literal, Protocol

if TYPE_CHECKING:
    from .context import CLIContext
    from .render.base import OutputRenderer


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS & TYPES
# ─────────────────────────────────────────────────────────────────────────────


class Command(Protocol):
    """Protocol for CLI commands."""

    name: str
    help: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace, ctx: Any, renderer: Any) -> int: ...


CommandGroup = Literal["execute", "observe", "verify", "maintain"]

# Display order for groups
GROUP_ORDER: tuple[CommandGroup, ...] = ("execute", "observe", "verify", "maintain")

# Human-readable group titles
GROUP_TITLES: dict[CommandGroup, str] = {
    "execute": "Execute",
    "observe": "Observe",
    "verify": "Verify",
    "maintain": "Maintain",
}


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND METADATA
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CommandMeta:
    """Presentation metadata for a command (used by home/help screens)."""

    group: CommandGroup
    one_liner: str
    examples: tuple[str, ...] = ()
    show_on_home: bool = False


@dataclass(frozen=True)
class CommandSpec:
    """Unified command specification: execution logic + presentation metadata."""

    cmd: Command
    meta: CommandMeta


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND IMPORTS
# ─────────────────────────────────────────────────────────────────────────────

from .commands.solve import COMMAND as SOLVE_COMMAND
from .commands.list import COMMAND as LIST_COMMAND
from .commands.show import COMMAND as SHOW_COMMAND
from .commands.events import COMMAND as EVENTS_COMMAND
from .commands.insight import COMMAND as INSIGHT_COMMAND
from .commands.explain import COMMAND as EXPLAIN_COMMAND
from .commands.version import COMMAND as VERSION_COMMAND
from .commands.new import COMMAND as NEW_COMMAND
from .commands.validate_ports import COMMAND as VALIDATE_COMMAND
from .commands.diagnostics import COMMAND as DIAGNOSTICS_COMMAND
from .commands.migrate import COMMAND as MIGRATE_COMMAND
from .commands.view import COMMAND as VIEW_COMMAND
from .commands.browse import COMMAND as BROWSE_COMMAND
from .commands.artifacts import COMMAND as ARTIFACTS_COMMAND
from .commands.ps import COMMAND as PS_COMMAND
from .commands.help import COMMAND as HELP_COMMAND


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED REGISTRY (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY: Dict[str, CommandSpec] = {
    # ── Execute ──────────────────────────────────────────────────────────────
    "solve": CommandSpec(
        cmd=SOLVE_COMMAND,
        meta=CommandMeta(
            group="execute",
            one_liner="Run an episode with an adapter/flow",
            examples=('noesis solve react "Weekly plan"',),
        ),
    ),
    # ── Observe ──────────────────────────────────────────────────────────────
    "ps": CommandSpec(
        cmd=PS_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Show a compact table of recent episodes",
            examples=("noesis ps", "noesis ps --limit 10"),
            show_on_home=True,
        ),
    ),
    "view": CommandSpec(
        cmd=VIEW_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Inspect timeline, metrics, and governance",
            examples=("noesis view <episode_id>",),
            show_on_home=True,
        ),
    ),
    "list": CommandSpec(
        cmd=LIST_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="List recent episodes",
            examples=("noesis list",),
        ),
    ),
    "show": CommandSpec(
        cmd=SHOW_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Show a single episode summary",
            examples=("noesis show <episode_id>",),
        ),
    ),
    "events": CommandSpec(
        cmd=EVENTS_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Print or stream episode events",
            examples=("noesis events <episode_id>",),
            show_on_home=True,
        ),
    ),
    "browse": CommandSpec(
        cmd=BROWSE_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Interactive episode browser (TUI)",
            examples=("noesis browse", "noesis browse -n 100"),
            show_on_home=True,
        ),
    ),
    "insight": CommandSpec(
        cmd=INSIGHT_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Show computed insight metrics",
            examples=("noesis insight <episode_id>",),
        ),
    ),
    "explain": CommandSpec(
        cmd=EXPLAIN_COMMAND,
        meta=CommandMeta(
            group="observe",
            one_liner="Explain why an episode was vetoed",
            examples=("noesis explain <episode_id>",),
            show_on_home=True,
        ),
    ),
    # ── Verify ───────────────────────────────────────────────────────────────
    "artifacts": CommandSpec(
        cmd=ARTIFACTS_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Manifest utilities and verification",
            examples=("noesis artifacts verify <episode_id>",),
            show_on_home=True,
        ),
    ),
    "validate-ports": CommandSpec(
        cmd=VALIDATE_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Validate configured runtime ports",
            examples=("noesis validate-ports",),
        ),
    ),
    "diagnostics": CommandSpec(
        cmd=DIAGNOSTICS_COMMAND,
        meta=CommandMeta(
            group="verify",
            one_liner="Stability diagnostics and replay compare",
            examples=("noesis diagnostics replay <episode_id>",),
            show_on_home=True,
        ),
    ),
    # ── Maintain ─────────────────────────────────────────────────────────────
    "migrate": CommandSpec(
        cmd=MIGRATE_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Codemod deprecated shims to the modern API",
            examples=("noesis migrate --check",),
        ),
    ),
    "version": CommandSpec(
        cmd=VERSION_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Print CLI and core versions",
            examples=("noesis version",),
        ),
    ),
    "new": CommandSpec(
        cmd=NEW_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Scaffold a starter flow or policy",
            examples=("noesis new flow my_flow",),
        ),
    ),
    "help": CommandSpec(
        cmd=HELP_COMMAND,
        meta=CommandMeta(
            group="maintain",
            one_liner="Show help for commands",
            examples=("noesis help", "noesis help view"),
        ),
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPAT: COMMANDS dict for existing call sites
# ─────────────────────────────────────────────────────────────────────────────

COMMANDS: Dict[str, Command] = {name: spec.cmd for name, spec in REGISTRY.items()}


# ─────────────────────────────────────────────────────────────────────────────
# QUERY HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def get_specs_by_group(group: CommandGroup) -> list[CommandSpec]:
    """Get all command specs in a group, sorted by name."""
    return sorted(
        [spec for spec in REGISTRY.values() if spec.meta.group == group],
        key=lambda s: s.cmd.name,
    )


def get_home_specs() -> list[CommandSpec]:
    """Get commands flagged for home screen display."""
    return [spec for spec in REGISTRY.values() if spec.meta.show_on_home]


def get_all_groups() -> tuple[CommandGroup, ...]:
    """Get all group names in display order."""
    return GROUP_ORDER


# ─────────────────────────────────────────────────────────────────────────────
# ARGPARSE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────


def register_commands(
    subparsers: argparse._SubParsersAction,
    *,
    parents: list[argparse.ArgumentParser],
    formatter_class: type[argparse.HelpFormatter],
) -> None:
    """Register all commands with argparse subparsers."""
    for name, spec in REGISTRY.items():
        command = spec.cmd
        parser = subparsers.add_parser(
            command.name,
            help=command.help,
            formatter_class=formatter_class,
            parents=parents,
        )
        command.add_arguments(parser)
        parser.set_defaults(command_obj=command)
