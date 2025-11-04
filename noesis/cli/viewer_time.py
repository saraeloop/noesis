from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_iso(timestamp: str) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp using stdlib, falling back to dateutil when available."""
    if not isinstance(timestamp, str):
        return None
    normalized = timestamp
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        try:  # pragma: no cover - optional dependency path
            from dateutil.parser import isoparse  # type: ignore
        except Exception:
            return None
        try:
            return isoparse(timestamp)
        except Exception:
            return None
