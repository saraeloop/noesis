from __future__ import annotations

import sys


def test_import_usecases_shim_is_lazy() -> None:
    sys.modules.pop("noesis.usecases.episode_runner", None)
    import noesis.usecases  # noqa: F401
    assert "noesis.usecases.episode_runner" not in sys.modules


def test_import_infrastructure_shim_is_lazy() -> None:
    sys.modules.pop("noesis.infrastructure.state_repository", None)
    import noesis.infrastructure  # noqa: F401
    assert "noesis.infrastructure.state_repository" not in sys.modules


def test_usecases_shim_resolves_episode_runner_symbol() -> None:
    import noesis.usecases as usecases

    _ = usecases.EpisodeRunner
