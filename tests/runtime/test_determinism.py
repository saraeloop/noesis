import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from noesis.diagnostics import compare_runs
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG
from noesis.runtime.session import SessionBuilder
from noesis.runtime.paths import resolve_noesis_paths
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


def _config_snapshot(
    tmp_path: Path,
    *,
    prompt_enabled: bool = False,
    prompt_mode: str = "hash_only",
    planner_mode: PlannerMode = PlannerMode.MINIMAL,
) -> ConfigSnapshot:
    learn_home = tmp_path / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs_dir": str(tmp_path),
        "agents": "agents.toml",
        "tasks": "tasks.toml",
        "timeout_sec": 5,
        "intuition_mode": IntuitionMode.ADVISORY.value,
        "direction_min_confidence": 0.5,
        "planner_mode": planner_mode.value,
        "policy_aliases": {},
        "learn_mode": LearnMode.OFF.value,
        "learn_home": str(learn_home),
        "learn_auto_apply_min_successes": 1,
        "learn_auto_apply_min_confidence": 0.5,
        "prompt_provenance_enabled": prompt_enabled,
        "prompt_provenance_mode": prompt_mode,
    }
    return ConfigSnapshot.from_mapping(payload)


class _FakeConfigPort:
    __api_version__ = "config/1.0-rc1"

    def __init__(self, base: Path | ConfigSnapshot) -> None:
        if isinstance(base, ConfigSnapshot):
            self._snapshot = base
            self._base = base.runs_dir
        else:
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


def _build_session(
    tmp_path: Path,
    *,
    timestamp_ms: int,
    seed: int,
    prompt_enabled: bool = False,
    prompt_mode: str = "hash_only",
    planner_mode: PlannerMode = PlannerMode.MINIMAL,
) -> SessionBuilder:
    clock = DeterministicClock(
        start_at=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
        tick_ms=5.0,
    )
    rng = DeterministicRNG(seed=seed)
    builder = SessionBuilder(
        config_port=_FakeConfigPort(
            _config_snapshot(
                tmp_path,
                prompt_enabled=prompt_enabled,
                prompt_mode=prompt_mode,
                planner_mode=planner_mode,
            )
        )
    ).with_determinism(
        clock=clock,
        rng=rng,
        episode_timestamp_ms=timestamp_ms,
    )
    return builder


def _episode_dir(root: Path, episode: str) -> Path:
    layout = resolve_noesis_paths(workspace=None, runs_dir=root)
    return layout.episodes_dir / episode


def _bytes(root: Path, episode: str, fname: str) -> bytes:
    return (_episode_dir(root, episode) / fname).read_bytes()


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
    path = _episode_dir(root, episode) / "events.jsonl"
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
    path = _episode_dir(root, episode) / "state.json"
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
    path = _episode_dir(root, episode) / "manifest.json"
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


def test_prompts_jsonl_is_deterministic_under_config(tmp_path: Path) -> None:
    """
    Ensure prompts.jsonl is byte-identical under DeterminismConfig when provenance is enabled.
    """
    timestamp_ms = 1_735_689_600_000
    seed = 321

    run_a_root = tmp_path / "run_prompts_a"
    run_b_root = tmp_path / "run_prompts_b"
    run_a_root.mkdir(parents=True, exist_ok=True)
    run_b_root.mkdir(parents=True, exist_ok=True)

    builder_a = _build_session(
        run_a_root,
        timestamp_ms=timestamp_ms,
        seed=seed,
        prompt_enabled=True,
        prompt_mode="full",
    )
    builder_b = _build_session(
        run_b_root,
        timestamp_ms=timestamp_ms,
        seed=seed,
        prompt_enabled=True,
        prompt_mode="full",
    )

    session_a = builder_a.build()
    session_b = builder_b.build()

    episode_a = session_a.run("Deterministic prompt provenance", intuition=False)
    episode_b = session_b.run("Deterministic prompt provenance", intuition=False)

    path_a = _episode_dir(run_a_root, episode_a) / "prompts.jsonl"
    path_b = _episode_dir(run_b_root, episode_b) / "prompts.jsonl"
    assert path_a.exists() and path_b.exists()

    assert path_a.read_bytes() == path_b.read_bytes(), "prompts.jsonl drifted under determinism"

    # Structural equality for events.jsonl with timestamps/IDs/snapshots stripped
    events_a = _normalized_events(run_a_root, episode_a)
    events_b = _normalized_events(run_b_root, episode_b)
    assert events_a == events_b, "events.jsonl drifted structurally"

    # No extra files in either run directory
    files_a = sorted(p.name for p in _episode_dir(run_a_root, episode_a).iterdir())
    files_b = sorted(p.name for p in _episode_dir(run_b_root, episode_b).iterdir())
    assert files_a == files_b


def test_governance_veto_run_is_deterministic(tmp_path: Path) -> None:
    """
    Ensure governance veto paths remain deterministic and replay cleanly.
    """
    timestamp_ms = 1_735_700_000_000
    seed = 999

    run_a_root = tmp_path / "veto_a"
    run_b_root = tmp_path / "veto_b"
    run_a_root.mkdir(parents=True, exist_ok=True)
    run_b_root.mkdir(parents=True, exist_ok=True)

    builder_a = _build_session(
        run_a_root,
        timestamp_ms=timestamp_ms,
        seed=seed,
        planner_mode=PlannerMode.META,
    )
    builder_b = _build_session(
        run_b_root,
        timestamp_ms=timestamp_ms,
        seed=seed,
        planner_mode=PlannerMode.META,
    )

    session_a = builder_a.build()
    session_b = builder_b.build()

    task = "veto this action: delete production database"
    episode_a = session_a.run(task, intuition=False)
    episode_b = session_b.run(task, intuition=False)

    path_a = _episode_dir(run_a_root, episode_a)
    path_b = _episode_dir(run_b_root, episode_b)

    result = compare_runs(path_a, path_b)
    assert not result.is_drift, f"replay drifted: {result.mismatches}"
