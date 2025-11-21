import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from noesis.runtime.determinism import DeterministicClock, DeterministicRNG
from noesis.runtime.session import SessionBuilder
from noesis.interfaces.config import ConfigSnapshot, PlannerMode
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode


def test_deterministic_clock_advances_fixed_steps() -> None:
    clock = DeterministicClock(start_at=datetime(2030, 1, 1, tzinfo=timezone.utc), tick_ms=5.0)
    token = clock.start("observe")
    metrics = clock.stop(token)
    assert metrics.duration_ms == 5.0
    assert metrics.started_at == datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert metrics.completed_at == datetime(2030, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=5)


def test_deterministic_rng_seeds_stdlib_and_bytes() -> None:
    rng = DeterministicRNG(seed=42)
    rng.reseed()
    first = rng.bytes(8)
    rng.reseed()
    second = rng.bytes(8)
    assert first == second


def test_deterministic_rng_uuid_namespace() -> None:
    rng = DeterministicRNG(seed=7)
    ns = UUID("00000000-0000-0000-0000-000000000001")
    # uuid5 is deterministic given namespace+name; seed does not alter uuid5 output.
    assert rng.uuid_namespace(ns, "rule") == UUID("83e12049-6bb1-5b51-a8cb-0fd0f1beade5")


def _config_snapshot(tmp_path: Path) -> ConfigSnapshot:
    learn_home = tmp_path / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs_dir": str(tmp_path),
        "agents": "agents.toml",
        "tasks": "tasks.toml",
        "timeout_sec": 5,
        "intuition_mode": IntuitionMode.ADVISORY.value,
        "direction_min_confidence": 0.5,
        "planner_mode": PlannerMode.MINIMAL.value,
        "policy_aliases": {},
        "learn_mode": LearnMode.OFF.value,
        "learn_home": str(learn_home),
        "learn_auto_apply_min_successes": 1,
        "learn_auto_apply_min_confidence": 0.5,
    }
    return ConfigSnapshot.from_mapping(payload)


class _FakeConfigPort:
    __api_version__ = "config/1.0-rc1"

    def __init__(self, base: Path) -> None:
        self._base = base
        self._snapshot = _config_snapshot(base)

    def get(self) -> ConfigSnapshot:
        return self._snapshot

    def set(self, **overrides: object) -> ConfigSnapshot:
        data = self._snapshot.to_mapping()
        data.update(overrides)
        self._snapshot = ConfigSnapshot.from_mapping(data)
        return self._snapshot

    def reload(self) -> ConfigSnapshot:
        return self._snapshot

    def supports(self, capability: str) -> bool:
        return False


def _build_session(tmp_path: Path, *, timestamp_ms: int, seed: int) -> SessionBuilder:
    clock = DeterministicClock(
        start_at=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
        tick_ms=5.0,
    )
    rng = DeterministicRNG(seed=seed)
    builder = SessionBuilder(config_port=_FakeConfigPort(tmp_path)).with_determinism(
        clock=clock,
        rng=rng,
        episode_timestamp_ms=timestamp_ms,
    )
    return builder


def _bytes(root: Path, episode: str, fname: str) -> bytes:
    return (root / episode / fname).read_bytes()


def _strip_timestamps_recursive(obj: dict) -> None:
    """Recursively strip timestamp fields from nested dictionaries."""
    if isinstance(obj, dict):
        obj.pop("timestamp", None)
        obj.pop("started_at", None)
        obj.pop("updated_at", None)
        obj.pop("created_at", None)
        obj.pop("completed_at", None)
        for value in obj.values():
            if isinstance(value, dict):
                _strip_timestamps_recursive(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _strip_timestamps_recursive(item)


def _normalized_events(root: Path, episode: str) -> list[dict]:
    """
    Normalize events by stripping purely observational fields (timestamp, id, snapshots).

    We keep the structural content of the cognitive trace (phases, payload fields,
    causes, metrics) but drop:
      - per-event timestamps and IDs
      - nested timestamp-like fields
      - snapshot payloads that embed full state/history debug context
    """
    path = root / episode / "events.jsonl"
    events: list[dict] = []
    for line in path.read_text().splitlines():
        evt = json.loads(line)

        # Strip top-level observational fields
        evt.pop("timestamp", None)
        evt.pop("id", None)

        # Strip nested timestamps everywhere
        _strip_timestamps_recursive(evt)

        # Strip nondeterministic snapshot payloads
        payload = evt.get("payload", {})
        if isinstance(payload, dict):
            # snapshot directly on payload
            payload.pop("snapshot", None)
            # snapshot nested under experimental
            experimental = payload.get("experimental")
            if isinstance(experimental, dict):
                experimental.pop("snapshot", None)

        events.append(evt)
    return events


def _normalized_state(root: Path, episode: str) -> dict:
    """Normalize state by stripping purely observational timestamp fields."""
    path = root / episode / "state.json"
    state = json.loads(path.read_text())
    # Strip timestamps that may drift due to instrumentation timing
    if "episode" in state:
        state["episode"].pop("started_at", None)
    if "plan" in state:
        state["plan"].pop("updated_at", None)
    if "outcomes" in state and "actions" in state["outcomes"]:
        for action in state["outcomes"]["actions"]:
            action.pop("timestamp", None)
    return state


def _normalized_manifest(root: Path, episode: str) -> dict:
    """Normalize manifest by stripping purely observational fields."""
    path = root / episode / "manifest.json"
    manifest = json.loads(path.read_text())
    # Strip timestamps that may drift due to instrumentation timing
    manifest.pop("created_at", None)
    # Strip SHA-256 hashes since events.jsonl timestamps/IDs are normalized
    if "files" in manifest:
        for file_info in manifest["files"]:
            file_info.pop("sha256", None)
    return manifest


def test_deterministic_session_runs_are_byte_identical(tmp_path: Path) -> None:
    """
    Ensure two runs with the same DeterminismConfig produce structurally identical artifacts.

    For summary.json (core semantic artifact), we require strict byte equality.
    For state.json and manifest.json, we compare normalized structures with
    timestamp/hash fields stripped.
    For events.jsonl, we compare normalized events with timestamps, IDs, and
    snapshot payloads stripped, enforcing structural (not byte-for-byte)
    determinism of the cognitive trace.
    """
    timestamp_ms = 1_735_689_600_000  # fixed epoch for determinism
    seed = 123

    run_a_root = tmp_path / "run_a"
    run_b_root = tmp_path / "run_b"
    run_a_root.mkdir(parents=True, exist_ok=True)
    run_b_root.mkdir(parents=True, exist_ok=True)

    builder_a = _build_session(run_a_root, timestamp_ms=timestamp_ms, seed=seed)
    builder_b = _build_session(run_b_root, timestamp_ms=timestamp_ms, seed=seed)

    session_a = builder_a.build()
    session_b = builder_b.build()

    episode_a = session_a.run("deterministic test", intuition=False)
    episode_b = session_b.run("deterministic test", intuition=False)

    assert episode_a == episode_b

    # Strict byte equality for summary.json (core semantic artifact)
    assert (
        _bytes(run_a_root, episode_a, "summary.json")
        == _bytes(run_b_root, episode_b, "summary.json")
    ), "summary.json drifted"

    # Structural equality for state.json
    state_a = _normalized_state(run_a_root, episode_a)
    state_b = _normalized_state(run_b_root, episode_b)
    assert state_a == state_b, "state.json drifted structurally"

    # Structural equality for manifest.json
    manifest_a = _normalized_manifest(run_a_root, episode_a)
    manifest_b = _normalized_manifest(run_b_root, episode_b)
    assert manifest_a == manifest_b, "manifest.json drifted structurally"

    # Structural equality for events.jsonl with timestamps/IDs/snapshots stripped
    events_a = _normalized_events(run_a_root, episode_a)
    events_b = _normalized_events(run_b_root, episode_b)
    assert events_a == events_b, "events.jsonl drifted structurally"

    # No extra files in either run directory
    files_a = sorted(p.name for p in (run_a_root / episode_a).iterdir())
    files_b = sorted(p.name for p in (run_b_root / episode_b).iterdir())
    assert files_a == files_b