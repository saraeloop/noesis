"""Deprecated module. Import from `noesis.runtime.utils` instead."""

from __future__ import annotations

from warnings import warn

from .utils import *  # noqa: F401,F403

warn(
    "noesis.runtime._utils is deprecated and will be removed in v0.9.0; "
    "import from noesis.runtime.utils instead.",
    DeprecationWarning,
    stacklevel=2,
)
