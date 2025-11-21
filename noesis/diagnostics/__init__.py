"""
Diagnostics helpers.

Public surface keeps replay/compare helpers importable without spelunking through
CLI internals.
"""

from __future__ import annotations

from .replay import DriftMismatch, DriftResult, compare_runs

__all__ = ["DriftMismatch", "DriftResult", "compare_runs"]
