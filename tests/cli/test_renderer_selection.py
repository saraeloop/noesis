from __future__ import annotations

import pytest

from noesis.cli.context import GlobalOptions
from noesis.cli.main import _HAS_RICH, _select_renderer
from noesis.cli.render.plain import PlainRenderer


class _DummyContext:
    isatty = False


def test_force_rich_selects_rich_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    rich = pytest.importorskip("rich")
    if not _HAS_RICH:
        pytest.skip("rich not installed")
    from noesis.cli.render.richy import RichRenderer

    monkeypatch.delenv("NO_COLOR", raising=False)
    renderer = _select_renderer(_DummyContext(), GlobalOptions(force_rich=True))
    assert isinstance(renderer, RichRenderer)
    assert not isinstance(renderer, PlainRenderer)


def test_no_color_forces_plain_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    renderer = _select_renderer(_DummyContext(), GlobalOptions(force_rich=True))
    assert isinstance(renderer, PlainRenderer)
    monkeypatch.delenv("NO_COLOR", raising=False)


def test_json_forces_plain_renderer() -> None:
    renderer = _select_renderer(_DummyContext(), GlobalOptions(json=True))
    assert isinstance(renderer, PlainRenderer)


def test_quiet_forces_plain_renderer() -> None:
    renderer = _select_renderer(_DummyContext(), GlobalOptions(quiet=True))
    assert isinstance(renderer, PlainRenderer)
