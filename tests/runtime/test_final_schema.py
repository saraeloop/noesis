from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

import noesis as ns
from noesis.domain.artifacts.finalization import FINAL_FILE_NAME, FINAL_SCHEMA_VERSION
from noesis.runtime.paths import resolve_noesis_paths


def test_emitted_final_json_conforms_to_v2_schema(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs-final-schema"
    learn_dir = tmp_path / "learn-final-schema"
    original = ns.get()
    ns.set(
        runs_dir=str(runs_dir),
        learn_home=str(learn_dir),
        planner_mode="minimal",
        governance_mode="off",
    )

    try:
        episode_id = ns.run(task="final schema conformance", intuition=False)
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        final_path = layout.episodes_dir / episode_id / FINAL_FILE_NAME
        assert final_path.exists()

        payload = json.loads(final_path.read_text(encoding="utf-8"))
        schema_path = Path(__file__).resolve().parents[2] / "docs" / "schema" / "final" / "2.0.0.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(instance=payload, schema=schema)
        assert payload["schema_version"] == FINAL_SCHEMA_VERSION
    finally:
        ns.set(**original)
