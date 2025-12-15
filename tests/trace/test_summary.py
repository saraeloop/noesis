from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import noesis as ns
from noesis.trace.events import read_events, write_event
from noesis.direction import DirectedIntuition
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION
from noesis.io import list_runs


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_metrics_keys_dedup(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    learn_dir = tmp_path / "learn"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir), planner_mode="minimal", governance_mode="off")

    episode_id = ns.run(task="Metrics sanity check", intuition=False)
    summary = ns.summary.read(episode_id)
    metrics = summary["metrics"]

    # Baseline signals
    assert metrics["success"] == 1  # baseline run() terminates with status 'ok'
    assert "veto_rate" not in metrics
    assert "top_reasons" in metrics
    assert "plan_count" in metrics
    assert "reflect_count" in metrics
    assert metrics.get("act_count") == metrics.get("steps")
    assert "interpret_count" in metrics
    assert isinstance(metrics.get("latencies", {}), dict)
    assert metrics.get("learn_proposals") == 0
    assert metrics.get("learn_applied") == 0
    # No direction/governance-derived fields in minimal mode
    assert "experimental" not in metrics
    assert "direction_veto_rate" not in metrics
    assert "direction_top_reasons" not in metrics
    assert "action_efficiency" not in metrics

    insight = summary["insight"]["metrics"]
    assert insight["success"] is True
    assert isinstance(insight["plan_revisions"], int)

    # restore
    ns.set(
        runs_dir=original["runs_dir"],
        learn_home=original["learn_home"],
        planner_mode=original.get("planner_mode", "meta"),
    )


def test_duration_and_mode_flags(tmp_path: Path):
    runs_dir = tmp_path / "runs-duration"
    learn_dir = tmp_path / "learn-duration"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir), planner_mode="minimal")

    episode_id = ns.run(task="Duration check", intuition=False)
    summary = ns.summary.read(episode_id)

    assert summary["duration_sec"] > 0.0
    assert summary["flags"]["mode"] == "off"
    assert summary["flags"]["intuition"] is False

    # restore
    ns.set(
        runs_dir=original["runs_dir"],
        learn_home=original["learn_home"],
        planner_mode=original.get("planner_mode", "meta"),
    )


def test_direction_policy_omitted_when_absent(tmp_path: Path):
    runs_dir = tmp_path / "runs-policy"
    learn_dir = tmp_path / "learn-policy"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir), planner_mode="minimal")

    episode_id = ns.run(task="No policy episode", intuition=False)
    direction_flags = ns.summary.read(episode_id)["flags"]["direction"]

    assert "policy" not in direction_flags

    # restore
    ns.set(
        runs_dir=original["runs_dir"],
        learn_home=original["learn_home"],
        planner_mode=original.get("planner_mode", "meta"),
    )


def test_success_metric(tmp_path: Path):
    runs_dir = tmp_path / "runs-success"
    learn_dir = tmp_path / "learn-success"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir), planner_mode="minimal")

    class Adapter:
        def run(self, task):
            return {"result": task}

    episode_id = ns.solve("Success task", using=lambda: Adapter(), intuition=False)
    summary = ns.summary.read(episode_id)
    metrics = summary["metrics"]

    assert metrics["success"] == 1
    assert summary["insight"]["metrics"]["success"] is True

    # restore
    ns.set(
        runs_dir=original["runs_dir"],
        learn_home=original["learn_home"],
        planner_mode=original.get("planner_mode", "meta"),
    )


def test_minimal_mode_events_and_insight_clean(tmp_path: Path):
    runs_dir = tmp_path / "runs-minimal-clean"
    learn_dir = tmp_path / "learn-minimal-clean"
    original = ns.get()
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir), planner_mode="minimal", governance_mode="off")

    try:
        episode_id = ns.run(task="Minimal mode cleanliness", intuition=False)
        summary = ns.summary.read(episode_id)
        events = list(ns.events.read(episode_id))

        assert all(event.get("phase") != "direction" for event in events)
        governance_events = [event for event in events if event.get("phase") == "governance"]
        # Minimal mode with governance off should emit no governance events; if mode flips, allow presence.
        if summary["flags"].get("mode") == "off":
            assert governance_events == []

        insight_metrics = summary["insight"]["metrics"]
        assert insight_metrics["veto_count"] == 0
        assert insight_metrics.get("plan_revisions", 0) == 0
    finally:
        # restore
        ns.set(
            runs_dir=original["runs_dir"],
            learn_home=original["learn_home"],
            planner_mode=original.get("planner_mode", "meta"),
            governance_mode=original.get("governance_mode", "off"),
        )


def test_schema_version_export():
    from noesis.trace.schema import SUMMARY_SCHEMA_VERSION as SCHEMA_VER
    assert ns.__schema_version__ == SCHEMA_VER


def test_insight_phase_validates(tmp_path: Path):
    run_dir = tmp_path / "events"
    event = {
        "timestamp": _iso_now(),
        "episode_id": "ep_demo",
        "agent_id": "system",
        "phase": "insight",
        "payload": {"metrics": {"steps": 1}},
        "evidence_ids": [],
    }

    write_event(run_dir, event)
    events = read_events(run_dir)
    assert events and events[0]["phase"] == "insight"


def test_latency_metrics_positive(tmp_path: Path):
    runs_dir = tmp_path / "runs-latency"
    learn_dir = tmp_path / "learn-latency"
    ns.set(runs_dir=str(runs_dir), learn_home=str(learn_dir))  # default planner: meta

    class VetoImmediately(DirectedIntuition):
        def advise(self, state):
            return self.veto(advice="Stop immediately.")

    class NoopGraph:
        def invoke(self, payload):
            return payload

    # A vetoing intuition in meta mode raises NoesisVeto by design.
    # Catch it so we can assert latency/insight metrics written by the summary.
    try:
        ns.solve(
            "Latency check",
            using=lambda: NoopGraph(),
            intuition=VetoImmediately(),
        )
    except Exception as exc:
        if exc.__class__.__name__ != "NoesisVeto":
            raise

    # Grab the latest episode written under this runs_dir
    episode_id = list_runs(limit=1)[0]["episode_id"]

    summary = ns.summary.read(episode_id)
    metrics = summary["metrics"]
    latencies = metrics.get("latencies", {})

    # time to veto must be recorded and positive
    assert latencies.get("time_to_veto_ms") is not None
    assert latencies["time_to_veto_ms"] >= 1

    # if a first action latency exists (some adapters may emit), it must be sane
    first_action = latencies.get("first_action_ms")
    if first_action is not None:
        assert first_action >= 1

    insight = summary["insight"]["metrics"]
    assert insight["veto_count"] >= 1
