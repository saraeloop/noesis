from __future__ import annotations

from noesis.runtime import (
    ensure_act_event,
    start_event,
)
from noesis.trace.events import read_events


def test_runtime_events_smoke(tmp_path):
    run_dir = tmp_path / "episode"
    episode_id = "ep-runtime"

    start_event(run_dir, episode_id, {"task": "demo"})
    ensure_act_event(
        run_dir,
        episode_id,
        adapter_label="adapter.test",
        input_excerpt="demo",
        outcome="ok",
    )

    events = read_events(run_dir)
    phases = [evt["phase"] for evt in events]

    assert "start" in phases
    assert "act" in phases
