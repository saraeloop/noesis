"""Deprecated module. Import from `noesis.summary` instead."""

from __future__ import annotations

from warnings import warn

from .summary import *  # noqa: F401,F403

warn(
    "noesis.runtime._summary is deprecated and will be removed in v0.9.0; "
    "import from noesis.summary instead.",
    DeprecationWarning,
    stacklevel=2,
)
