import json
from pathlib import Path

import noesis as ns
import pytest
from noesis.learn import maybe_emit_learn_event
from noesis.context import get_config_port
from noesis.domain.learning.errors import MissingCausalLinkError
from noesis.runtime.paths import resolve_noesis_paths


def _direction_events(policy_id: str, policy_version: str | None = None) -> list[dict]:
    payload = {
        "policy": policy_id,
        "policy_version": policy_version,
        "status": "blocked",
        "reason": "veto",
        "confidence": 0.9,
    }
    return [
        {"id": "direction-1", "phase": "direction", "payload": payload},
        {"id": "reflect-1", "phase": "reflect", "payload": {"reasons": ["veto"]}},
        {"id": "terminate-1", "phase": "terminate", "payload": {"status": "ok"}},
    ]


def _metrics(direction_vetoed: int = 1, direction_events: int = 1) -> dict:
    return {
        "direction_vetoed": direction_vetoed,
        "direction_events": direction_events,
        "plan_count": 0,
        "steps": 0,
        "reflect_count": 1,
        "latencies": {},
        "direction_applied": 0,
    }


def test_learn_auto_apply_gate(tmp_path):
    cfg_port = get_config_port()
    baseline = cfg_port.get()
    try:
        runs_dir = tmp_path / "runs"
        learn_home = tmp_path / "learn"
        ns.set(
            runs_dir=str(runs_dir),
            learn_mode="apply",
            learn_home=str(learn_home),
            direction_min_confidence=0.3,
            learn_auto_apply_min_confidence=0.1,
            learn_auto_apply_min_successes=2,
        )

        policy_id = "unit.Policy"
        events = _direction_events(policy_id, policy_version="1.0")
        metrics = _metrics()

        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        layout.episodes_dir.mkdir(parents=True, exist_ok=True)

        for idx in range(2):
            run_dir = layout.episodes_dir / f"ep_{idx}"
            run_dir.mkdir(parents=True)
            result = maybe_emit_learn_event(
                run_dir=run_dir,
                episode_id=f"ep_{idx}",
                events=list(events),
                metrics=dict(metrics),
                config=get_config_port().get(),
            )
            assert result is not None

        cfg_after = cfg_port.get().to_mapping()
        assert float(cfg_after["direction_min_confidence"]) > 0.3

        policy_snapshot_path = Path(learn_home) / "policies" / "unit.Policy.json"
        assert policy_snapshot_path.exists()
        snapshot = json.loads(policy_snapshot_path.read_text(encoding="utf-8"))
        assert snapshot["gates"]["direction_min_confidence"]["successes"] == 0
        history_entry = snapshot["history"][-1]
        assert history_entry["status"] == "applied"
        assert history_entry["revert_handle"]["previous"] == 0.3

        learn_log = list((layout.episodes_dir / "ep_1" / "learn.jsonl").read_text(encoding="utf-8").splitlines())
        assert learn_log, "expected learn log for applied proposal"
        record = json.loads(learn_log[-1])
        assert record["schema_version"] == "learn/1.0"
        payload = record["payload"]
        proposal = payload["proposal"][0]
        assert proposal["status"] == "applied"
        assert proposal["revert_handle"]["previous"] == 0.3
        assert payload["approval"] == "auto-applied"
    finally:
        cfg_port.set(**baseline.to_mapping())


def test_learn_emit_rejects_missing_upstream_event_id(tmp_path) -> None:
    cfg_port = get_config_port()
    baseline = cfg_port.get()
    try:
        runs_dir = tmp_path / "runs"
        learn_home = tmp_path / "learn"
        ns.set(
            runs_dir=str(runs_dir),
            learn_mode="record",
            learn_home=str(learn_home),
            direction_min_confidence=0.3,
            learn_auto_apply_min_confidence=0.1,
            learn_auto_apply_min_successes=1,
        )

        events = [
            {
                "phase": "direction",
                "payload": {
                    "policy": "unit.Policy",
                    "policy_version": "1.0",
                    "status": "blocked",
                    "reason": "veto",
                    "confidence": 0.9,
                },
            },
            {"phase": "reflect", "payload": {"reasons": ["veto"]}},
        ]
        run_dir = resolve_noesis_paths(workspace=None, runs_dir=runs_dir).episodes_dir / "ep_missing_reflect_id"
        run_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(MissingCausalLinkError) as exc:
            maybe_emit_learn_event(
                run_dir=run_dir,
                episode_id="ep_missing_reflect_id",
                events=events,
                metrics=_metrics(),
                config=get_config_port().get(),
            )

        assert "upstream event id" in str(exc.value)
        learn_path = run_dir / "learn.jsonl"
        assert learn_path.exists()
        assert learn_path.read_text(encoding="utf-8") == ""
    finally:
        cfg_port.set(**baseline.to_mapping())
