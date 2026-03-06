from __future__ import annotations

from noesis.domain.tool_contract import ToolIdentity, ToolProtocol, fingerprint_payload, fingerprint_prepared_invocation


def test_payload_fingerprint_is_order_independent() -> None:
    left = {"b": 2, "a": {"x": 1, "y": 2}}
    right = {"a": {"y": 2, "x": 1}, "b": 2}

    assert fingerprint_payload(left) == fingerprint_payload(right)


def test_prepared_invocation_fingerprint_changes_with_payload() -> None:
    tool = ToolIdentity(namespace="repo", name="write_file", version="1")

    baseline = fingerprint_prepared_invocation(
        protocol=ToolProtocol.SUBPROCESS,
        tool=tool,
        normalized_payload={"path": "README.md", "content": "hello"},
    )
    changed = fingerprint_prepared_invocation(
        protocol=ToolProtocol.SUBPROCESS,
        tool=tool,
        normalized_payload={"path": "README.md", "content": "goodbye"},
    )

    assert baseline != changed
