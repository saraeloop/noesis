from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from noesis.domain.faculties import (
    GovernanceResult,
    InsightMetrics,
    IntuitionEvent,
    PlannerDirective,
)
from noesis.trace.schema import schema_path


GOLDEN_DIR = Path(__file__).parent


def _load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_schema(name: str) -> dict[str, object]:
    with open(schema_path(name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_intuition_payload_schema_round_trip() -> None:
    payload = _load_json(GOLDEN_DIR / "intuition_event.json")
    validate(instance=payload, schema=_load_schema("intuition"))
    event = IntuitionEvent.from_dict(payload)
    assert event.to_dict() == payload


def test_direction_payload_schema_round_trip() -> None:
    payload = _load_json(GOLDEN_DIR / "direction_directive.json")
    validate(instance=payload, schema=_load_schema("direction"))
    directive = PlannerDirective.from_mapping(payload)
    assert directive.to_mapping() == payload


def test_governance_payload_schema_round_trip() -> None:
    payload = _load_json(GOLDEN_DIR / "governance_result.json")
    validate(instance=payload, schema=_load_schema("governance"))
    result = GovernanceResult.from_mapping(payload)
    assert result.to_mapping() == payload


def test_insight_payload_schema_round_trip() -> None:
    payload = _load_json(GOLDEN_DIR / "insight_metrics.json")
    validate(instance=payload, schema=_load_schema("insight"))
    metrics = InsightMetrics.from_mapping(payload)
    assert metrics.to_mapping() == payload
