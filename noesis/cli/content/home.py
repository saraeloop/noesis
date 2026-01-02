"""Home screen content model, derived from registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..registry import REGISTRY, get_specs_by_group


@dataclass(frozen=True)
class QuickStartItem:
    """A quick start example command with description."""

    command: str
    description: str


@dataclass(frozen=True)
class CommandPreview:
    """A command preview for grouped display on home screen."""

    name: str
    one_liner: str


@dataclass(frozen=True)
class RecentEpisode:
    """A recent episode for home screen preview (summary-only data)."""

    time_str: str  # HH:MM
    episode_short: str  # truncated ID (middle ellipsis)
    status: str  # success | vetoed | error
    task: str  # truncated task
    duration: str  # e.g., "0.8s"


@dataclass(frozen=True)
class HomeScreen:
    """Home screen content model."""

    version: str
    tagline: str
    quick_start: tuple[QuickStartItem, ...]
    recent_episodes: tuple[RecentEpisode, ...]
    observe_commands: tuple[CommandPreview, ...]
    verify_commands: tuple[CommandPreview, ...]
    footer_hint: str


def build_home_screen(
    version: str,
    *,
    recent_episodes: Sequence[RecentEpisode] = (),
) -> HomeScreen:
    """
    Build home screen from registry metadata.

    Args:
        version: The Noēsis version string.
        recent_episodes: Optional list of recent episodes to display.

    Returns:
        A HomeScreen instance with all content derived from the registry.
    """
    # Quick start: curated set of commands with examples
    quick_start_names = ["run", "ps", "view"]
    quick_start = tuple(
        QuickStartItem(
            command=(
                REGISTRY[name].meta.examples[0]
                if REGISTRY[name].meta.examples
                else f"noesis {name}"
            ),
            description=REGISTRY[name].meta.one_liner,
        )
        for name in quick_start_names
        if name in REGISTRY
    )

    # Observe group (show_on_home only)
    observe = tuple(
        CommandPreview(name=spec.cmd.name, one_liner=spec.meta.one_liner)
        for spec in get_specs_by_group("observe")
        if spec.meta.show_on_home
    )

    # Verify group (show_on_home only)
    verify = tuple(
        CommandPreview(name=spec.cmd.name, one_liner=spec.meta.one_liner)
        for spec in get_specs_by_group("verify")
        if spec.meta.show_on_home
    )

    return HomeScreen(
        version=version,
        tagline="Observable episodes · Governance · Deterministic replay",
        quick_start=quick_start,
        recent_episodes=tuple(recent_episodes),
        observe_commands=observe,
        verify_commands=verify,
        footer_hint="noesis help",
    )
