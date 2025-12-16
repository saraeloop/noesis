"""Curated re-exports for intuition configuration.

Most users configure intuition via noesis.set(intuition_mode=...) and observe
artifacts. For policy authoring, see noesis.direction (DirectedIntuition).
"""

from noesis.domain.faculties.intuition import (
    Intuition,
    IntuitionEvent,
    IntuitionMode,
    NullIntuition,
)

__all__ = [
    "Intuition",
    "IntuitionEvent",
    "IntuitionMode",
    "NullIntuition",
]

