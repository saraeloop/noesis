from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate

from noesis.domain.run_lifecycle import (
    RUN_LIFECYCLE_STATE_MACHINE_SCHEMA_VERSION,
    RUN_LIFECYCLE_TRANSITIONS,
    TERMINAL_RUN_STATES,
    RunLifecycleTransitionError,
    assert_valid_transition,
    lifecycle_state_machine_snapshot,
)


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "schema" / "run_lifecycle" / "1.0.0.json"


def test_lifecycle_state_machine_snapshot_matches_schema() -> None:
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    snapshot = lifecycle_state_machine_snapshot()
    validate(instance=snapshot, schema=schema)
    assert snapshot["schema_version"] == RUN_LIFECYCLE_STATE_MACHINE_SCHEMA_VERSION


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for state in TERMINAL_RUN_STATES:
        assert RUN_LIFECYCLE_TRANSITIONS[state] == frozenset()


def test_valid_lifecycle_transitions_cover_runtime_and_governance_outcomes() -> None:
    assert_valid_transition("running", "interrupted")
    assert_valid_transition("running", "paused")
    assert_valid_transition("paused", "resuming")
    assert_valid_transition("running", "vetoed")
    assert_valid_transition("running", "cancelled")
    assert_valid_transition("running", "error")


def test_invalid_transition_from_terminal_state_is_rejected() -> None:
    with pytest.raises(RunLifecycleTransitionError, match="invalid run lifecycle transition"):
        assert_valid_transition("vetoed", "resuming")
