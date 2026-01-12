from __future__ import annotations

from .base import OutputRenderer

__all__ = ["OutputRenderer", "PlainRenderer"]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "PlainRenderer":
        from .plain import PlainRenderer
        return PlainRenderer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
