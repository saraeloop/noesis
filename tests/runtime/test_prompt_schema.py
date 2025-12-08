from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "artifacts"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schema" / "prompt" / "1.1.0.json"


def _load_schema() -> dict[str, object]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_lines(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_prompts_full_fixture_matches_schema() -> None:
    schema = _load_schema()
    for record in _load_lines(FIXTURE_DIR / "prompts_full.jsonl"):
        validate(instance=record, schema=schema)


def test_prompts_hash_only_fixture_matches_schema() -> None:
    schema = _load_schema()
    for record in _load_lines(FIXTURE_DIR / "prompts_hash_only.jsonl"):
        validate(instance=record, schema=schema)
