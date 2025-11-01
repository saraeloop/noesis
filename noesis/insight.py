"""Compatibility surface for historical `noesis.insight` imports."""

from __future__ import annotations

import warnings

from .domain.faculties.insight import compute_metrics

__all__ = ["compute_metrics"]

warnings.warn(
    "noesis.insight is deprecated; import from noesis.domain.faculties.insight",
    DeprecationWarning,
    stacklevel=2,
)
