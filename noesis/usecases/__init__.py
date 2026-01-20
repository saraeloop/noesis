"""
Use-case layer (application services) for Noēsis.

This package defines orchestrators (e.g., EpisodeRunner) and ports that
separate domain logic from infrastructure concerns.
"""

__all__ = [
    "EpisodeRunner",
    "EpisodeDependencies",
    "EpisodeInstrumentation",
    "EpisodeRequest",
    "EpisodeResult",
    "EpisodeOutcome",
]


def __getattr__(name: str):  # pragma: no cover - import shim
    if name in __all__:
        from . import episode_runner as _episode_runner

        return getattr(_episode_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
