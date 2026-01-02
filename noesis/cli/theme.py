"""Theme tokens, layout constants, and breakpoints for CLI rendering."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


# ─────────────────────────────────────────────────────────────────────────────
# BREAKPOINTS
# ─────────────────────────────────────────────────────────────────────────────


class Breakpoint(Enum):
    """Terminal width breakpoints for adaptive layouts."""

    COMPACT = "compact"  # < 60 cols (mobile-like, single column)
    STANDARD = "standard"  # 60-99 cols (typical split terminal)
    WIDE = "wide"  # >= 100 cols (full-width terminal)


# Breakpoint thresholds
COMPACT_MAX = 60
STANDARD_MAX = 100


def detect_breakpoint(width: int) -> Breakpoint:
    """Detect breakpoint from terminal width."""
    if width < COMPACT_MAX:
        return Breakpoint.COMPACT
    if width < STANDARD_MAX:
        return Breakpoint.STANDARD
    return Breakpoint.WIDE


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ThemeLayout:
    """Layout constants for consistent spacing."""

    panel_padding: tuple[int, int] = (1, 2)  # vertical, horizontal
    panel_width: int = 88  # default panel width
    max_width: int = 100  # cap for very wide terminals
    min_width: int = 40  # minimum for compact mode
    gutter: int = 2  # space between columns
    indent: int = 2  # standard indent
    command_col_width: int = 14  # command name column
    description_col_width: int = 40  # description column


# ─────────────────────────────────────────────────────────────────────────────
# THEME TOKENS
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ThemeTokens:
    """Theme tokens for consistent styling."""

    styles: Mapping[str, str]
    layout: ThemeLayout = ThemeLayout()


def build_theme_tokens() -> ThemeTokens:
    """Build the complete theme token set."""
    return ThemeTokens(
        styles={
            # ── Core text styles ─────────────────────────────────────────────
            "title": "bold bright_cyan",
            "accent": "bright_cyan",
            "muted": "grey66",
            "hint": "dim",
            # ── Key-value pairs ──────────────────────────────────────────────
            "key": "bright_cyan",
            "val": "white",
            # ── Status indicators ────────────────────────────────────────────
            "ok": "green",
            "warn": "yellow",
            "err": "bold red",
            # ── Structural elements ──────────────────────────────────────────
            "border": "grey42",
            "panel": "grey50",
            "header": "bold bright_cyan",
            # ── Badges ───────────────────────────────────────────────────────
            "badge": "black on bright_cyan",
            "badge.version": "black on bright_cyan",
            "badge.success": "bold white on green",
            "badge.warn": "bold black on yellow",
            "badge.error": "bold white on red",
            # ── Navigation ───────────────────────────────────────────────────
            "nav.arrow": "bright_blue",
            "nav.command": "bold bright_cyan",
            # ── Group headers ────────────────────────────────────────────────
            "group.title": "bold bright_cyan",
            # ── Home screen ──────────────────────────────────────────────────
            "home.tagline": "italic grey74",
            "hero.badge": "bold white on blue",
            "hero.art": "bright_blue",
            "hero.prompt": "grey70",
            "hero.accent": "bold bright_blue",
            "hero.border": "blue",
            # ── Phase colors (for timeline/events) ───────────────────────────
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
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENFORCED STYLE: One border/box style everywhere
# ─────────────────────────────────────────────────────────────────────────────


def get_box_style():
    """
    Return the single box style used across all Rich panels/tables.

    This enforces visual consistency: home panels, help panels, dashboard
    tables, and all other Rich surfaces use the same border style.

    Returns None if Rich is not available.
    """
    try:
        from rich import box

        return box.ROUNDED
    except ImportError:
        return None
