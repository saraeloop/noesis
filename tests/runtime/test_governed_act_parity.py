from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

import noesis as ns
import noesis.core as core
from noesis.runtime.paths import resolve_noesis_paths
from noesis.trace.events import read_events


@contextmanager
def _preserve_config():
    original = ns.get()
    try:
        yield
    finally:
        ns.set(**original)


def _episode_dirs(runs_dir: Path) -> dict[str, Path]:
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
    return {
        path.name: path
        for path in layout.episodes_dir.iterdir()
        if path.is_dir() and path.name.startswith("ep_")
    } if layout.episodes_dir.exists() else {}


def _new_episode_id(before: dict[str, Path], after: dict[str, Path]) -> str:
    created = [episode_id for episode_id in after if episode_id not in before]
    assert len(created) == 1
    return created[0]


def _assert_sealed_contract(run_dir: Path) -> None:
    final_path = run_dir / "final.json"
    manifest_path = run_dir / "manifest.json"
    assert final_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert any(entry.get("name") == "final.json" for entry in manifest.get("files", []))


def _assert_pause_contract(run_dir: Path) -> None:
    events = read_events(run_dir)
    governance_event = next(event for event in events if event.get("phase") == "governance")
    interrupt_event = next(
        event
        for event in events
        if event.get("phase") == "runtime" and event.get("event_type") == "run.interrupt"
    )
    checkpoint_event = next(
        event
        for event in events
        if event.get("phase") == "runtime" and event.get("event_type") == "run.checkpoint"
    )
    assert interrupt_event.get("caused_by") == governance_event["id"]
    assert checkpoint_event.get("caused_by") == interrupt_event["id"]
    assert not any(event.get("phase") == "act" for event in events)
    assert not any(event.get("phase") == "terminate" for event in events)
    assert not (run_dir / "final.json").exists()
    assert not (run_dir / "manifest.json").exists()


def test_governed_act_allow_path_matches_canonical_sealing(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    class NoopGraph:
        def invoke(self, payload):
            return payload

    def run_shell(*, command: str):
        return {"ok": True, "command": command}

    with _preserve_config():
        ns.set(
            runs_dir=str(runs_dir),
            planner_mode="minimal",
            governance_mode="enforce",
            governance_pause_on_veto=False,
            shell_executor=run_shell,
        )

        before_governed = _episode_dirs(runs_dir)
        result = ns.governed_act(
            goal="safe operation: list repository files",
            kind="shell",
            payload={"command": "ls -a"},
        )
        after_governed = _episode_dirs(runs_dir)
        governed_episode_id = _new_episode_id(before_governed, after_governed)
        governed_run_dir = after_governed[governed_episode_id]

        canonical_episode_id = ns.solve(
            task="safe operation: list repository files",
            using=NoopGraph(),
            intuition=False,
        )
        canonical_run_dir = _episode_dirs(runs_dir)[canonical_episode_id]

        assert result == {"ok": True, "command": "ls -a"}
        _assert_sealed_contract(governed_run_dir)
        _assert_sealed_contract(canonical_run_dir)


def test_governed_act_veto_pause_matches_canonical_pause_contract(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    governed_side_effect = workspace / "governed-side-effect.txt"
    canonical_side_effect = workspace / "canonical-side-effect.txt"

    class MutatingGraph:
        def invoke(self, payload):
            canonical_side_effect.write_text(str(payload), encoding="utf-8")
            return payload

    def run_shell(*, command: str):
        governed_side_effect.write_text(command, encoding="utf-8")
        return {"ok": True, "command": command}

    with _preserve_config():
        ns.set(
            runs_dir=str(runs_dir),
            planner_mode="minimal",
            governance_mode="enforce",
            governance_pause_on_veto=True,
            shell_executor=run_shell,
        )

        before_governed = _episode_dirs(runs_dir)
        with pytest.raises(ns.NoesisVeto):
            ns.governed_act(
                goal="Danger operation: delete production database",
                kind="shell",
                payload={"command": "echo blocked"},
            )
        after_governed = _episode_dirs(runs_dir)
        governed_episode_id = _new_episode_id(before_governed, after_governed)
        governed_run_dir = after_governed[governed_episode_id]

        canonical_episode_id = ns.solve(
            task="Danger operation: delete production database",
            using=MutatingGraph(),
            intuition=False,
            workspace=workspace,
        )
        canonical_run_dir = _episode_dirs(runs_dir)[canonical_episode_id]

        assert not governed_side_effect.exists()
        assert not canonical_side_effect.exists()
        _assert_pause_contract(governed_run_dir)
        _assert_pause_contract(canonical_run_dir)


def test_governed_act_uses_canonical_core_sealing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir = tmp_path / "runs"

    def run_shell(*, command: str):
        return {"ok": True, "command": command}

    def fail_seal(**kwargs):
        raise RuntimeError("seal-path-failure")

    with _preserve_config():
        ns.set(
            runs_dir=str(runs_dir),
            planner_mode="minimal",
            governance_mode="enforce",
            governance_pause_on_veto=False,
            shell_executor=run_shell,
        )
        monkeypatch.setattr(core, "_seal_episode", fail_seal)

        with pytest.raises(RuntimeError, match="seal-path-failure"):
            ns.governed_act(
                goal="safe operation: list repository files",
                kind="shell",
                payload={"command": "ls -a"},
            )
