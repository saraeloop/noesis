"""Shared schema version helpers for faculty contracts."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Dict

FACULTY_SCHEMA_VERSIONS: Dict[str, str] = {
    "intuition": "1.1.0",
    "direction": "1.2.0",
    "governance": "1.1.0",
    "insight": "1.0.0",
}


def current_version(faculty: str) -> str:
    """Return the canonical schema version for the given faculty."""
    normalized = faculty.lower()
    if normalized not in FACULTY_SCHEMA_VERSIONS:
        raise KeyError(f"Unknown faculty '{faculty}'")
    return FACULTY_SCHEMA_VERSIONS[normalized]


@dataclass(frozen=True)
class VersionCompatibility:
    """Lightweight comparison result for schema compatibility checks."""

    requested: str
    current: str

    @property
    def is_compatible(self) -> bool:
        """Compatibility allows matching major versions and <= current minor."""
        req_major, req_minor = _major_minor(self.requested)
        cur_major, cur_minor = _major_minor(self.current)
        return req_major == cur_major and req_minor <= cur_minor


def is_compatible(requested: str, current: str) -> bool:
    """Return True when the requested schema version is compatible with current."""
    return VersionCompatibility(requested=requested, current=current).is_compatible


def _major_minor(version: str) -> tuple[int, int]:
    segments = version.split(".")
    if len(segments) < 2:
        raise ValueError(f"Invalid semantic version '{version}'")
    return int(segments[0]), int(segments[1])


def warn_on_incompatibility(faculty: str, requested: str) -> bool:
    """Emit a warning when a requested schema is incompatible with the current contract."""
    current = current_version(faculty)
    compatible = is_compatible(requested, current)
    if not compatible:
        warnings.warn(
            f"Faculty '{faculty}' schema '{requested}' is incompatible with current '{current}'.",
            stacklevel=2,
        )
    return compatible


__all__ = [
    "FACULTY_SCHEMA_VERSIONS",
    "current_version",
    "is_compatible",
    "warn_on_incompatibility",
    "VersionCompatibility",
]
