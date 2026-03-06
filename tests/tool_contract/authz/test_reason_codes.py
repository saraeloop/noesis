from __future__ import annotations

from noesis.domain.tool_contract.reason_codes import (
    ALL_REASON_CODES,
    AUTHN_FAILED,
    AUTHZ_DENIED,
    AUTHZ_MISSING_CONTEXT,
)


def test_authz_reason_codes_are_present_and_unique() -> None:
    assert AUTHN_FAILED in ALL_REASON_CODES
    assert AUTHZ_DENIED in ALL_REASON_CODES
    assert AUTHZ_MISSING_CONTEXT in ALL_REASON_CODES
    assert len(ALL_REASON_CODES) == len(set(ALL_REASON_CODES))
