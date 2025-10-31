"""Compatibility shim for directional policies."""

from noesis.domain.faculties.direction import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith("_")]
