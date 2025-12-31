from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from noesis.cli.view_models import build_episode_dashboard


def test_rich_viewer_output_contains_tables(demo_run: Path) -> None:
    pytest.importorskip("rich")
    from rich.console import Console
    from rich.theme import Theme

    from noesis.cli.render.richy import RichRenderer

    view = build_episode_dashboard(demo_run, validate=True)
    assert view.validation_issues == []

    console = Console(
        file=StringIO(),
        record=True,
        force_terminal=True,
        width=120,
        color_system=None,
        theme=Theme({"title": "bold"}),
    )
    renderer = RichRenderer(console)
    renderer.print_viewer(view)

    output = console.export_text()
    assert "KPIs" in output
    assert "Timeline" in output
    assert "┌" in output and "┐" in output, "expected table borders in rich output"
    # Check column headers exist (spacing may vary due to column widths)
    assert "Δt" in output and "PHASE" in output and "SUMMARY" in output
