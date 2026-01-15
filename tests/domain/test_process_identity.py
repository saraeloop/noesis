from __future__ import annotations

from noesis.domain.process import derive_process_identity


def test_process_identity_is_deterministic() -> None:
    identity_a = derive_process_identity(workspace_identity="/tmp/workspace")
    identity_b = derive_process_identity(workspace_identity="/tmp/workspace")

    assert identity_a.process_id == identity_b.process_id
    assert identity_a.process_name == identity_b.process_name


def test_process_identity_with_name_changes_id() -> None:
    identity_a = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")
    identity_b = derive_process_identity(workspace_identity="/tmp/workspace", process_name="beta")

    assert identity_a.process_id != identity_b.process_id
    assert identity_a.process_name == "alpha"
    assert identity_b.process_name == "beta"
