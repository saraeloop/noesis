"""Home screen content model, derived from registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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
    episode_id: str  # full ID
    status: str  # SUCCESS | VETOED | ERROR | AUDIT
    task: str  # truncated task
    duration: str  # e.g., "0.8s"
    outcome: str | None = None
    success: bool | None = None


@dataclass(frozen=True)
class LastEpisodeInfo:
    """Detailed info about the last episode for the home screen."""

    episode_id: str
    status: str  # SUCCESS | VETOED | ERROR | AUDIT
    duration: str
    task: str
    outcome: str | None = None
    success: bool | None = None
    # Governance veto details (only if vetoed)
    rule_id: str | None = None
    score: float | None = None
    message: str | None = None


@dataclass(frozen=True)
class ConfigSnapshot:
    """Current configuration snapshot for display."""

    governance_mode: str  # off | audit | enforce
    planner_mode: str  # minimal | meta
    intuition_mode: str  # off | advisory | required
    runs_dir: str


@dataclass(frozen=True)
class NextAction:
    """A suggested next action command."""

    command: str
    description: str


@dataclass(frozen=True)
class HomeScreen:
    """Home screen content model - status + action launcher."""

    version: str
    tagline: str
    config: ConfigSnapshot
    last_episode: LastEpisodeInfo | None
    recent_episodes: tuple[RecentEpisode, ...]
    next_actions: tuple[NextAction, ...]
    footer_hint: str

    # Legacy fields for backward compatibility
    quick_start: tuple[QuickStartItem, ...] = ()
    observe_commands: tuple[CommandPreview, ...] = ()
    verify_commands: tuple[CommandPreview, ...] = ()


def build_home_screen(
    version: str,
    *,
    config_snapshot: Mapping[str, Any] | None = None,
    recent_episodes: Sequence[RecentEpisode] = (),
    last_episode_id: str | None = None,
    last_episode_info: LastEpisodeInfo | None = None,
) -> HomeScreen:
    """
    Build home screen from registry metadata and runtime config.

    Args:
        version: The Noēsis version string.
        config_snapshot: Current config as a mapping.
        recent_episodes: Optional list of recent episodes to display.
        last_episode_id: Optional last episode ID for dynamic hint.
        last_episode_info: Detailed info about the last episode.

    Returns:
        A HomeScreen instance with all content derived from the registry.
    """
    config_snapshot = config_snapshot or {}

    # Build config display
    config = ConfigSnapshot(
        governance_mode=config_snapshot.get("governance_mode", "off"),
        planner_mode=config_snapshot.get("planner_mode", "minimal"),
        intuition_mode=config_snapshot.get("intuition_mode", "advisory"),
        runs_dir=str(config_snapshot.get("runs_dir", "./runs")),
    )

    # Build next actions based on state
    next_actions: list[NextAction] = []
    if last_episode_info and last_episode_info.status == "VETOED":
        # Vetoed episode - suggest explain, view, rerun
        next_actions = [
            NextAction(
                command=f"noesis explain {last_episode_info.episode_id}",
                description="why it was blocked + evidence",
            ),
            NextAction(
                command=f"noesis view {last_episode_info.episode_id}",
                description="timeline + KPIs",
            ),
            NextAction(
                command=f"noesis rerun {last_episode_info.episode_id} --audit",
                description="safe re-run (audit mode)",
            ),
        ]
    elif last_episode_id:
        next_actions = [
            NextAction(
                command=f"noesis view {last_episode_id}",
                description="inspect the last episode",
            ),
            NextAction(
                command="noesis run \"your task\"",
                description="start a new episode",
            ),
            NextAction(
                command="noesis browse",
                description="open TUI browser",
            ),
        ]
    else:
        next_actions = [
            NextAction(
                command="noesis run \"your task\"",
                description="start a new episode",
            ),
            NextAction(
                command="noesis browse",
                description="open TUI browser",
            ),
            NextAction(
                command="noesis help",
                description="see all commands",
            ),
        ]

    # Dynamic footer
    if last_episode_id:
        footer_hint = f"noesis view {last_episode_id}"
    else:
        footer_hint = "noesis help"

    # Legacy quick start (for backward compat with old renderers)
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
        tagline="Understanding, made observable.",
        config=config,
        last_episode=last_episode_info,
        recent_episodes=tuple(recent_episodes),
        next_actions=tuple(next_actions),
        footer_hint=footer_hint,
        quick_start=quick_start,
        observe_commands=observe,
        verify_commands=verify,
    )
