"""Theme tokens, layout constants, and breakpoints for CLI rendering."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


# ─────────────────────────────────────────────────────────────────────────────
# SYMBOLS (Modern geometric style)
# ─────────────────────────────────────────────────────────────────────────────

# Status symbols - used for episode status indicators
STATUS_SYMBOLS = {
    "SUCCESS": "●",
    "OK": "●",
    "VETOED": "✗",
    "VETO": "✗",
    "AUDIT": "⚠",
    "ERROR": "✗",
    "PENDING": "○",
    "UNKNOWN": "○",
}

# Phase symbols - used in timeline visualization
PHASE_SYMBOLS = {
    "start": "◆",
    "observe": "○",
    "intuition": "◇",
    "interpret": "◈",
    "plan": "▸",
    "governance": "◈",
    "direction": "→",
    "act": "●",
    "reflect": "↺",
    "learn": "◆",
    "insight": "◇",
    "memory": "◆",
    "terminate": "■",
    "error": "✗",
}

# Navigation symbols
NAV_ARROW = "→"
BULLET = "●"
DIAMOND = "◆"

# ASCII fallbacks for plain renderer
STATUS_SYMBOLS_ASCII = {
    "SUCCESS": "[OK]",
    "OK": "[OK]",
    "VETOED": "[VETO]",
    "VETO": "[VETO]",
    "AUDIT": "[!]",
    "ERROR": "[ERR]",
    "PENDING": "[ ]",
    "UNKNOWN": "[?]",
}

NAV_ARROW_ASCII = ">"
BULLET_ASCII = "*"


def section_line(title: str, width: int = 72) -> str:
    """Create a section header line: ─── title ─────────────────"""
    left = f"─── {title} "
    remaining = max(0, width - len(left))
    return left + "─" * remaining


def section_line_ascii(title: str, width: int = 72) -> str:
    """Create an ASCII section header line: --- title ---"""
    left = f"--- {title} "
    remaining = max(0, width - len(left))
    return left + "-" * remaining


def status_symbol(status: str, ascii_mode: bool = False) -> str:
    """Get the symbol for a status."""
    key = status.upper()
    if ascii_mode:
        return STATUS_SYMBOLS_ASCII.get(key, "[?]")
    return STATUS_SYMBOLS.get(key, "○")


def phase_symbol(phase: str) -> str:
    """Get the symbol for a phase."""
    return PHASE_SYMBOLS.get(phase.lower(), "○")


@dataclass(frozen=True)
class OutcomeBadge:
    """Visual label for a normalized outcome."""

    label: str
    symbol: str
    style: str


_OUTCOME_BADGES: Mapping[str, OutcomeBadge] = {
    "success": OutcomeBadge(label="SUCCESS", symbol="●", style="ok"),
    "success_unverified": OutcomeBadge(label="UNVERIFIED", symbol="●", style="warn"),
    "goal_not_achieved": OutcomeBadge(label="GOAL NOT ACHIEVED", symbol="●", style="err"),
    "violated": OutcomeBadge(label="VIOLATED", symbol="●", style="err"),
    "error": OutcomeBadge(label="ERROR", symbol="●", style="err"),
}


def outcome_badge(outcome: str | None) -> OutcomeBadge:
    """Return the badge metadata for an outcome."""
    key = (outcome or "").strip().lower()
    return _OUTCOME_BADGES.get(key, OutcomeBadge(label="UNKNOWN", symbol="●", style="muted"))


def normalize_outcome(
    outcome: str | None,
    *,
    status: str | None = None,
    success: object | None = None,
) -> str | None:
    """Best-effort normalization for legacy rows without outcome."""
    if isinstance(outcome, str) and outcome:
        return outcome
    if isinstance(status, str) and status:
        normalized = status.lower()
        if normalized == "vetoed":
            return "violated"
        if normalized == "error":
            return "error"
    if success is True:
        return "success"
    if success is False:
        return "error"
    return None


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
    """Build the complete theme token set - modern Charm/bubbletea inspired."""
    return ThemeTokens(
        styles={
            # ── Core text styles ─────────────────────────────────────────────
            "title": "bold",
            "subtitle": "bold bright_cyan",
            "accent": "bright_cyan",
            "muted": "bright_black",
            "dim": "bright_black",
            "hint": "italic bright_black",
            # ── Key-value pairs ──────────────────────────────────────────────
            "key": "bright_black",
            "val": "white",
            "label": "bright_black",
            # ── Status indicators (vibrant) ──────────────────────────────────
            "ok": "bright_green",
            "success": "bright_green",
            "warn": "bright_yellow",
            "err": "bold bright_red",
            "info": "bright_blue",
            # ── Status styles with symbols ───────────────────────────────────
            "status.success": "bold bright_green",
            "status.vetoed": "bold bright_red",
            "status.veto": "bold bright_red",
            "status.audit": "bold bright_yellow",
            "status.error": "bold bright_red",
            "status.pending": "bright_black",
            # ── Structural elements ──────────────────────────────────────────
            "border": "bright_black",
            "panel": "bright_black",
            "header": "bold",
            "separator": "bright_black",
            "section": "bright_black",
            # ── Brand ────────────────────────────────────────────────────────
            "brand": "bold bright_magenta",
            "version": "bright_magenta",
            "tagline": "bright_black",
            # ── Badges ───────────────────────────────────────────────────────
            "badge": "black on bright_cyan",
            "badge.version": "bold bright_magenta",
            "badge.success": "bold white on green",
            "badge.warn": "bold black on yellow",
            "badge.error": "bold white on red",
            # ── Navigation (bubbletea style) ─────────────────────────────────
            "nav.arrow": "bright_magenta",
            "nav.bullet": "bright_cyan",
            "nav.command": "bright_cyan",
            "nav.desc": "bright_black",
            # ── Group headers ────────────────────────────────────────────────
            "group.title": "bold bright_black",
            # ── Home screen ──────────────────────────────────────────────────
            "home.tagline": "bright_black",
            "home.brand": "bold bright_magenta",
            "home.version": "bright_magenta",
            "home.config.key": "bright_black",
            "home.config.val": "bright_cyan",
            "hero.badge": "bold white on blue",
            "hero.art": "bright_blue",
            "hero.prompt": "grey70",
            "hero.accent": "bold bright_blue",
            "hero.border": "blue",
            # ── Phase colors (for timeline/events) ───────────────────────────
            "phase.start": "bright_cyan",
            "phase.intuition": "bright_magenta",
            "phase.observe": "bright_blue",
            "phase.interpret": "bright_blue",
            "phase.plan": "bright_cyan",
            "phase.governance": "bright_yellow",
            "phase.direction": "bright_blue",
            "phase.insight": "bright_green",
            "phase.reason": "bright_black",
            "phase.act": "white",
            "phase.reflect": "bright_green",
            "phase.learn": "bright_cyan",
            "phase.memory": "bright_black",
            "phase.terminate": "bright_yellow",
            "phase.error": "bold bright_red",
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
