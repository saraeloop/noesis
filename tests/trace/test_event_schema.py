import json
from pathlib import Path

from jsonschema import validate

from noesis.trace.schema import EVENTS_SCHEMA_VERSION, events_schema_path


def _load_events_schema() -> dict:
    path = Path(events_schema_path(EVENTS_SCHEMA_VERSION))
    return json.loads(path.read_text(encoding="utf-8"))


def test_learn_event_schema_design_a() -> None:
    schema = _load_events_schema()
    event = {
        "id": "evt-1",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "episode_id": "ep-1",
        "phase": "learn",
        "payload": {
            "learn_path": "learn.jsonl",
            "learn_schema": "learn/1.0",
            "proposal_count": 1,
            "proposal_ids": ["policy:ep-1"],
            "applied": False,
        },
        "evidence_ids": [],
    }
    validate(instance=event, schema=schema)


def test_learn_event_schema_legacy_inline() -> None:
    schema = _load_events_schema()
    event = {
        "id": "evt-2",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "episode_id": "ep-2",
        "phase": "learn",
        "payload": {
            "policy_id": "policy.v1",
            "basis": {"success": True},
            "proposal": [],
            "scope": "policy",
        },
        "evidence_ids": [],
    }
    validate(instance=event, schema=schema)


def test_action_candidate_event_schema() -> None:
    schema = _load_events_schema()
    event = {
        "id": "evt-3",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "episode_id": "ep-3",
        "phase": "action_candidate",
        "payload": {
            "schema_version": "action_candidate/1.0.0",
            "action_candidate_id": "ac-123",
            "kind": "tool",
            "payload": {"tool_name": "fs.write", "args": {"path": "notes.txt"}},
            "state_ref": "state.json",
            "state_hash": "sha256:abc123",
            "redaction": {"mode": "hash_only", "policy_id": "redact.v1", "policy_version": "1.0.0", "field_rules": {}},
        },
        "evidence_ids": [],
    }
    validate(instance=event, schema=schema)
