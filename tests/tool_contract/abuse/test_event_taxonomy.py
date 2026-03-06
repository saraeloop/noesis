from __future__ import annotations

from noesis.domain.tool_contract.event_names import ALL_EVENT_NAMES, TOOL_RATE_LIMITED
from noesis.domain.tool_contract.reason_codes import ALL_REASON_CODES, RATE_LIMITED


def test_abuse_bucket_freezes_rate_limit_taxonomy() -> None:
    assert TOOL_RATE_LIMITED in ALL_EVENT_NAMES
    assert RATE_LIMITED in ALL_REASON_CODES
    assert len(ALL_EVENT_NAMES) == len(set(ALL_EVENT_NAMES))
