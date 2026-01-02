"""Help screen content model, derived from registry."""
from __future__ import annotations

from dataclasses import dataclass

from ..registry import REGISTRY, get_specs_by_group, get_all_groups, GROUP_TITLES, CommandGroup


@dataclass(frozen=True)
class CommandInfo:
    """Command info for help display."""

    name: str
    one_liner: str


@dataclass(frozen=True)
class CommandGroupInfo:
    """A group of commands for help display."""

    title: str
    commands: tuple[CommandInfo, ...]


@dataclass(frozen=True)
class HelpScreen:
    """Help screen content model."""

    version: str
    tagline: str
    usage: str
    groups: tuple[CommandGroupInfo, ...]
    examples: tuple[str, ...]
    footer: str


def build_help_screen(version: str) -> HelpScreen:
    """
    Build help screen from registry metadata.

    Args:
        version: The Noēsis version string.

    Returns:
        A HelpScreen instance with all content derived from the registry.
    """
    groups = tuple(
        CommandGroupInfo(
            title=GROUP_TITLES[group],
            commands=tuple(
                CommandInfo(name=spec.cmd.name, one_liner=spec.meta.one_liner)
                for spec in get_specs_by_group(group)
            ),
        )
        for group in get_all_groups()
    )

    # Collect first example from each command (up to 5)
    examples: list[str] = []
    for spec in REGISTRY.values():
        if spec.meta.examples:
            examples.append(spec.meta.examples[0])
        if len(examples) >= 5:
            break

    return HelpScreen(
        version=version,
        tagline="Run, inspect, and govern cognitive episodes.",
        usage="noesis <command> [options]",
        groups=groups,
        examples=tuple(examples),
        footer="Tip: noesis help <command> or noesis <command> -h for details.",
    )
