"""Deprecated module. Import from `noesis.learn` instead."""

from __future__ import annotations

from warnings import warn

from .learning import *  # noqa: F401,F403

warn(
    "noesis.runtime._learning is deprecated and will be removed in v0.9.0; "
    "import from noesis.learn instead.",
    DeprecationWarning,
    stacklevel=2,
)
