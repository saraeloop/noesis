import json
from pathlib import Path

import noesis as ns
from noesis import _config as _cfg
from noesis.runtime._learning import maybe_emit_learn_event


def _direction_events(policy_id: str, policy_version: str | None = None) -> list[dict]:
    payload = {
        "policy": policy_id,
        "policy_version": policy_version,
        "status": "blocked",
        "reason": "veto",
        "confidence": 0.9,
    }
    return [
        {"phase": "direction", "payload": payload},
        {"phase": "reflect", "payload": {"reasons": ["veto"]}},
        {"phase": "terminate", "payload": {"status": "ok"}},
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
    _cfg.reset()
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

        for idx in range(2):
            run_dir = runs_dir / f"ep_{idx}"
            run_dir.mkdir(parents=True)
            result = maybe_emit_learn_event(
                run_dir=run_dir,
                episode_id=f"ep_{idx}",
                events=list(events),
                metrics=dict(metrics),
            )
            assert result is not None

        cfg_after = _cfg.get()
        assert float(cfg_after["direction_min_confidence"]) > 0.3

        policy_snapshot_path = Path(learn_home) / "policies" / "unit.Policy.json"
        assert policy_snapshot_path.exists()
        snapshot = json.loads(policy_snapshot_path.read_text(encoding="utf-8"))
        assert snapshot["gates"]["direction_min_confidence"]["successes"] == 0
        history_entry = snapshot["history"][-1]
        assert history_entry["status"] == "applied"
        assert history_entry["revert_handle"]["previous"] == 0.3

        learn_log = list((runs_dir / "ep_1" / "learn.jsonl").read_text(encoding="utf-8").splitlines())
        assert learn_log, "expected learn log for applied proposal"
        payload = json.loads(learn_log[-1])["payload"]
        proposal = payload["proposal"][0]
        assert proposal["status"] == "applied"
        assert proposal["revert_handle"]["previous"] == 0.3
        assert payload["approval"] == "auto-applied"
    finally:
        _cfg.reset()
