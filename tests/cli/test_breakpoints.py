"""Tests for theme breakpoint detection."""
from __future__ import annotations

import pytest

from noesis.cli.theme import (
    Breakpoint,
    detect_breakpoint,
    COMPACT_MAX,
    STANDARD_MAX,
    get_box_style,
)


class TestBreakpointDetection:
    """Tests for terminal width breakpoint detection."""

    @pytest.mark.parametrize(
        "width,expected",
        [
            # Compact: < 60
            (20, Breakpoint.COMPACT),
            (40, Breakpoint.COMPACT),
            (59, Breakpoint.COMPACT),
            # Standard: 60-99
            (60, Breakpoint.STANDARD),
            (80, Breakpoint.STANDARD),
            (99, Breakpoint.STANDARD),
            # Wide: >= 100
            (100, Breakpoint.WIDE),
            (120, Breakpoint.WIDE),
            (200, Breakpoint.WIDE),
        ],
    )
    def test_detect_breakpoint(self, width: int, expected: Breakpoint):
        """Breakpoint detection returns correct value for width."""
        assert detect_breakpoint(width) == expected

    def test_compact_max_threshold(self):
        """COMPACT_MAX is the boundary between COMPACT and STANDARD."""
        assert detect_breakpoint(COMPACT_MAX - 1) == Breakpoint.COMPACT
        assert detect_breakpoint(COMPACT_MAX) == Breakpoint.STANDARD

    def test_standard_max_threshold(self):
        """STANDARD_MAX is the boundary between STANDARD and WIDE."""
        assert detect_breakpoint(STANDARD_MAX - 1) == Breakpoint.STANDARD
        assert detect_breakpoint(STANDARD_MAX) == Breakpoint.WIDE

    def test_breakpoint_values_are_strings(self):
        """Breakpoint enum values are human-readable strings."""
        assert Breakpoint.COMPACT.value == "compact"
        assert Breakpoint.STANDARD.value == "standard"
        assert Breakpoint.WIDE.value == "wide"


class TestBoxStyle:
    """Tests for the enforced box style."""

    def test_get_box_style_returns_rounded_when_rich_available(self):
        """get_box_style returns box.ROUNDED when Rich is available."""
        pytest.importorskip("rich")
        from rich import box

        result = get_box_style()
        assert result is box.ROUNDED

    def test_get_box_style_is_consistent(self):
        """get_box_style always returns the same object."""
        pytest.importorskip("rich")
        assert get_box_style() is get_box_style()
