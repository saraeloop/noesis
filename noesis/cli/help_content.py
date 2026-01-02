"""DEPRECATED: Use noesis.cli.content instead.

This module is a thin re-export for backward compatibility.
All content builders are now derived from the unified registry.
"""
from __future__ import annotations

# Re-export from new location for backward compatibility
from .content.home import (
    HomeScreen,
    QuickStartItem,
    CommandPreview,
    RecentEpisode,
    build_home_screen,
)
from .content.help import (
    HelpScreen,
    CommandGroupInfo,
    CommandInfo,
    build_help_screen,
)

# Legacy aliases for backward compatibility with existing code
CommandGroup = CommandGroupInfo

__all__ = [
    # Home screen
    "HomeScreen",
    "QuickStartItem",
    "CommandPreview",
    "RecentEpisode",
    "build_home_screen",
    # Help screen
    "HelpScreen",
    "CommandGroup",  # Legacy alias
    "CommandGroupInfo",
    "CommandInfo",
    "build_help_screen",
]


def iter_group_commands(groups):
    """DEPRECATED: Iterate over commands in groups."""
    for group in groups:
        for command in group.commands:
            yield command
