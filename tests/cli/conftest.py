from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialize the demo episode used by CLI viewer assertions."""
    run_dir = tmp_path_factory.mktemp("demo-run")
    (run_dir / "events.jsonl").write_text(
        """{"id":"11111111-1111-4999-aaaa-000000000001","timestamp":"2025-11-04T15:55:01.120000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"start","payload":{"task":"Danger operation: delete production database","seed":0},"evidence_ids":[]}
{"id":"11111111-1111-4999-aaaa-000000000002","timestamp":"2025-11-04T15:55:01.140000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"observe","payload":{"task":"Danger operation: delete production database","tags":{"environment":"demo"},"timestamp":"2025-11-04T15:55:01.140000+00:00","experimental":{"snapshot":{"task":"Danger operation: delete production database","seed":0,"history":[],"tools_seen":[],"tags":{"environment":"demo"},"state_path":"state.json","using":"core.meta"}}},"evidence_ids":[]}
{"id":"11111111-1111-4999-aaaa-000000000003","timestamp":"2025-11-04T15:55:01.160000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"interpret","payload":{"signals":[]},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000002"}
{"id":"11111111-1111-4999-aaaa-000000000004","timestamp":"2025-11-04T15:55:01.190000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"planner.meta","phase":"plan","payload":{"steps":["detect:Evaluate risk","act:Execute delete production database","verify:Confirm mitigation"],"rationale":"meta planner"},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000003"}
{"id":"11111111-1111-4999-aaaa-000000000005","timestamp":"2025-11-04T15:55:01.210000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"governance.rules","phase":"direction","payload":{"status":"blocked","applied":false,"reason":"governance_veto","rule_id":"rules.veto.danger","score":0.95,"policy":"governance.rules","policy_id":"governance.rules","policy_version":"1.0.0","policy_kind":"rules"},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000004"}
{"id":"11111111-1111-4999-aaaa-000000000006","timestamp":"2025-11-04T15:55:01.220000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"governance.rules","phase":"governance","payload":{"schema_version":"1.1.0","governance_id":"gov-demo-eab4a1f6c142","decision_id":"33333333-3333-4333-aaaa-000000000006","decision":"veto","rule_id":"rules.veto.danger","score":0.95,"message":"Task flagged as dangerous","policy_id":"governance.rules","policy_version":"1.0.0","policy_kind":"rules","mode":"enforce","failure_policy":"fail_closed","enforced":true,"details":{"goal":"Danger operation: delete production database"}},"evidence_ids":[],"caused_by":"11111111-1111-4999-aaaa-000000000005"}
{"id":"11111111-1111-4999-aaaa-000000000007","timestamp":"2025-11-04T15:55:01.300000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"terminate","payload":{"status":"vetoed","message":"Task flagged as dangerous"},"evidence_ids":[]}
{"id":"11111111-1111-4999-aaaa-000000000008","timestamp":"2025-11-04T15:55:01.320000+00:00","episode_id":"ep_20251104_155501_805857_c5f4_s0","agent_id":"system","phase":"insight","payload":{"metrics":{"success":0,"plan_adherence":0.0,"veto_count":1,"would_veto_count":0,"tool_coverage":0.0}},"evidence_ids":[]}""",
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        """{
  "schema_version": "1.3.0",
  "episode_id": "ep_20251104_155501_805857_c5f4_s0",
  "task": "Danger operation: delete production database",
  "seed": 0,
  "started_at": "2025-11-04T15:55:01.120000+00:00",
  "duration_sec": 0.18,
  "adapter_result": "skipped",
  "outcome": "error",
  "verification": {
    "provided": false,
    "passed": null,
    "assertions": [],
    "workspace_diff": null,
    "snapshots": null,
    "policy": {
      "ignore": [".git", "__pycache__", ".venv", ".noesis"],
      "symlinks": "skip"
    }
  },
  "flags": {
    "intuition": false,
    "mode": "off",
    "using": "core.meta",
    "governance_mode": "enforce",
    "governance_failure_policy": "fail_closed",
    "direction": {
      "applied": 0,
      "vetoed": 1,
      "last_diff": [],
      "threshold": 0.75,
      "policy": "governance.rules"
    }
  },
  "agents_config_hash": "sha256:demo",
  "metrics": {
    "success": 0,
    "plan_adherence": 0.0,
    "veto_count": 1,
    "would_veto_count": 0,
    "tool_coverage": 0.0,
    "direction_events": 1,
    "direction_applied": 0,
    "direction_vetoed": 1,
    "governance_vetoed": 1,
    "governance_would_vetoed": 0,
    "plan_count": 1,
    "reflect_count": 0,
    "act_count": 0,
    "steps": 0,
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
      "would_veto_count": 0,
      "tool_coverage": 0.0,
      "plan_revisions": 0,
      "phase_ms": {
        "plan": 30
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
