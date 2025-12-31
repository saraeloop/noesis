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
