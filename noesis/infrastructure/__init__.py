"""Infrastructure layer exports for Noēsis."""

__all__ = ["config", "RuntimeStateRepository"]


def __getattr__(name: str):  # pragma: no cover - import shim
    if name == "config":
        from . import config as _config

        return _config
    if name == "RuntimeStateRepository":
        from .state_repository import RuntimeStateRepository

        return RuntimeStateRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
