from __future__ import annotations

from noesis import events
from noesis.trace.events import read_events


def test_runtime_events_smoke(tmp_path):
    run_dir = tmp_path / "episode"
    episode_id = "ep-runtime"

    events.start(run_dir, episode_id, {"task": "demo"})
    events.ensure(
        run_dir,
        episode_id,
        adapter_label="adapter.test",
        input_excerpt="demo",
        outcome="ok",
    )

    recorded = read_events(run_dir)
    phases = [evt["phase"] for evt in recorded]

    assert "start" in phases
    assert "act" in phases
