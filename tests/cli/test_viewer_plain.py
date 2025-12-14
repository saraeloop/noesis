from __future__ import annotations

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import noesis
import pytest

from noesis.cli.render.plain import PlainRenderer
from noesis.cli.viewer import load_episode_view


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialize the demo episode used by viewer assertions."""
    run_dir = tmp_path_factory.mktemp("demo-run")
    (run_dir / "events.jsonl").write_text(
        """{"id":"11111111-1111-4999-aaaa-000000000001","timestamp":"2025-11-04T15:55:01.120000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"start","payload":{"task":"Danger operation: delete production database","seed":0},"evidence_ids":[]}
{"id":"11111111-1111-4999-aaaa-000000000002","timestamp":"2025-11-04T15:55:01.140000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"observe","payload":{"task":"Danger operation: delete production database","tags":{"environment":"demo"}},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000001"}
{"id":"11111111-1111-4999-aaaa-000000000003","timestamp":"2025-11-04T15:55:01.160000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"interpret","payload":{"signals":["danger","high-risk"],"reasons":["goal contains 'delete'"]},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000002"}
{"id":"11111111-1111-4999-aaaa-000000000004","timestamp":"2025-11-04T15:55:01.190000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"planner.meta","phase":"plan","payload":{"steps":["detect:Evaluate risk","act:Execute delete production database","verify:Confirm mitigation"],"rationale":"meta planner"},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000003"}
{"id":"11111111-1111-4999-aaaa-000000000005","timestamp":"2025-11-04T15:55:01.210000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"governance.rules","phase":"governance","payload":{"schema_version":"1.1.0","governance_id":"gov-demo-eab4a1f6c142","decision_id":"33333333-3333-4333-aaaa-000000000005","decision":"veto","rule_id":"rules.veto.danger","score":0.95,"message":"Task flagged as dangerous","policy_id":"governance.rules","policy_version":"1.0.0","policy_kind":"rules","details":{"goal":"Danger operation: delete production database"}},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000004"}
{"id":"11111111-1111-4999-aaaa-000000000006","timestamp":"2025-11-04T15:55:01.220000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"governance.rules","phase":"direction","payload":{"schema_version":"1.1.0","directive_id":"dir-demo-4f6b7c5d92aa","legacy_directive_id":"44444444-4444-4444-aaaa-000000000006","policy":"governance.rules","policy_id":"governance.rules","policy_version":"1.0.0","policy_kind":"rules","status":"blocked","reason":"veto","applied":false,"steps":["governance:veto"],"diff":[]},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000005"}
{"id":"11111111-1111-4999-aaaa-000000000007","timestamp":"2025-11-04T15:55:01.230000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"adapter:core.meta","phase":"act","payload":{"input_excerpt":"Evaluate risk","adapter":"adapter:core.meta","outcome":"blocked","reasons":["rules.veto.danger"]},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000006"}
{"id":"11111111-1111-4999-aaaa-000000000008","timestamp":"2025-11-04T15:55:01.250000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"reflect","payload":{"success":false,"reasons":["rules.veto.danger"]},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000007"}
{"id":"11111111-1111-4999-aaaa-000000000009","timestamp":"2025-11-04T15:55:01.260000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"learn","payload":{"policy_id":"policy:core.meta","basis":["rules.veto.danger"],"proposal":[],"applied":false,"scope":"episode"},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000008"}
{"id":"11111111-1111-4999-aaaa-00000000000a","timestamp":"2025-11-04T15:55:01.270000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"insight","payload":{"metrics":{"success":0,"plan_adherence":0.0,"veto_count":1,"tool_coverage":0.0}},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000009"}
{"id":"11111111-1111-4999-aaaa-00000000000b","timestamp":"2025-11-04T15:55:01.300000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"terminate","payload":{"status":"vetoed","message":"Task flagged as dangerous"},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000008"}""",
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        """{
  "schema_version": "1.2.0",
  "episode_id": "ep_20251104_155501_805857_c5f4_s0",
  "task": "Danger operation: delete production database",
  "seed": 0,
  "started_at": "2025-11-04T15:55:01.120000+00:00",
  "duration_sec": 0.18,
  "flags": {
    "intuition": false,
    "mode": "off",
    "using": "adapter:core.meta",
    "direction": {
      "applied": 0,
      "vetoed": 1,
      "last_diff": [],
      "threshold": 0.75,
      "policy": "governance.rules",
      "mode": "off"
    }
  },
  "agents_config_hash": "sha256:demo",
  "metrics": {
    "success": 0,
    "plan_adherence": 0.0,
    "veto_count": 1,
    "tool_coverage": 0.0,
    "direction_events": 1,
    "direction_applied": 0,
    "direction_vetoed": 1,
    "steps": 3,
    "top_reasons": [
      "rules.veto.danger"
    ],
    "latencies": {
      "time_to_veto_ms": 30
    }
  },
  "insight": {
    "metrics": {
      "success": false,
      "plan_adherence": 0.0,
      "veto_count": 1,
      "tool_coverage": 0.0,
      "plan_revisions": 0,
      "phase_ms": {
        "plan": 30,
        "governance": 10,
        "act": 5
      }
    }
  },
  "tags": {
    "environment": "demo"
  },
  "ports": {
    "memory": "memory/sqlite",
    "insight": "insight/json"
  }
}""",
        encoding="utf-8",
    )
    return run_dir


def test_plain_viewer_output_matches_fixture(demo_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(demo_run.parent)

    view = load_episode_view(str(demo_run), ns=noesis, runtime_context=None)
    assert view.validation == []

    renderer = PlainRenderer()
    buffer = StringIO()
    with redirect_stdout(buffer):
        renderer.print_viewer(view)
    output_lines = buffer.getvalue().splitlines()

    normalized = [line.rstrip() for line in output_lines]
    assert normalized[0] == "Episode"
    assert "  planner_mode: off" in normalized
    assert "  intuition   : off" in normalized
    assert any("policies" in line and "governance.rules" in line for line in normalized)

    assert "KPIs" in normalized
    assert any("plan_adherence" in line and "0.0" in line for line in normalized)
    assert any("veto_count" in line and "1" in line for line in normalized)

    assert "Governance" in normalized
    assert any("decision" in line and "veto" in line for line in normalized)
    assert any("rule_id" in line and "rules.veto.danger" in line for line in normalized)

    timeline = [line for line in normalized if line.strip().startswith("[")]

    def has_phase(phase: str, needle: str | None = None) -> bool:
        for line in timeline:
            if f" {phase:<10} " in line:
                if needle is None or needle in line:
                    return True
        return False

    assert has_phase("start", "Danger operation")
    assert has_phase("governance", "veto")
    assert has_phase("direction", "blocked")
    assert has_phase("act", "blocked")
    assert has_phase("reflect")
    assert has_phase("terminate", "Task flagged as dangerous")
