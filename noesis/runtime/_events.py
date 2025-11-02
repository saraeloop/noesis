"""Deprecated module. Import from `noesis.events` instead."""

from __future__ import annotations

from warnings import warn

from .events import *  # noqa: F401,F403

warn(
    "noesis.runtime._events is deprecated and will be removed in v0.9.0; "
    "import from noesis.events instead.",
    DeprecationWarning,
    stacklevel=2,
)
