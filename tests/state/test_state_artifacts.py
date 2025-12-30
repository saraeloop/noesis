import json
from pathlib import Path

import noesis as ns
from noesis.episode import EpisodeIndex
from noesis.context import get_config_port


def test_state_artifact_written(tmp_path) -> None:
    cfg_port = get_config_port()
    baseline = cfg_port.get()
    try:
        runs_dir = tmp_path / "runs"
        ns.set(runs_dir=str(runs_dir))
        episode = ns.run(task="hello state", intuition=False)
        state_path = runs_dir / episode / "state.json"
        assert state_path.exists(), "state.json not persisted"

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload["episode"]["id"] == episode
        assert payload["goal"]["task"] == "hello state"
        assert payload["plan"]["steps"], "plan steps absent"
        step = payload["plan"]["steps"][0]
        assert step["kind"] in {"detect", "plan"}
        assert step["status"] in {"pending", "done", "failed", "vetoed", "running", "skipped"}
        assert payload["outcomes"]["status"] == "ok"
        actions = payload["outcomes"]["actions"]
        assert actions and {"id", "kind", "tool", "result_status"}.issubset(actions[0].keys())
        assert payload["episode"]["using"] in {"core.minimal", "core.null"}
        assert payload["version"] == "1.0"
        assert payload["state_schema_version"] == "1.0.0"
        assert payload["links"]["events"] == "events.jsonl"
        assert payload["links"]["summary"] == "summary.json"
    finally:
        cfg_port.set(**baseline.to_mapping())


def test_episode_store_ttl_and_search(tmp_path) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text("{}", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    store = EpisodeIndex(tmp_path / "store", ttl_days=0, enable_faiss=True)
    store.append(
        episode_id="ep_test",
        summary_path=summary_path,
        state_path=state_path,
        status="ok",
        task="demo",
        using="adapter:test",
        provenance={"schema_version": "1.0", "state_schema_version": "1.0.0"},
        embedding=[0.1, 0.2, 0.3],
    )

    # TTL=0 marks record expired immediately.
    assert list(store.iter()) == []
    assert [r.episode_id for r in store.iter(include_expired=True)] == ["ep_test"]

    removed = store.vacuum()
    assert removed == 1
    assert list(store.iter(include_expired=True)) == []

    # Similarity search safely returns empty when FAISS is unavailable.
    assert store.search([0.1, 0.2, 0.3]) == []
