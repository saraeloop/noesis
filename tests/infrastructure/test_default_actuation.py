from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import noesis.core as core
from noesis.context import create_runtime_context
from noesis.domain.faculties.governance import GovernanceFailurePolicy, GovernanceMode
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.infrastructure.actuation.default_actuation import DefaultActuationPort, governed_act_impl
from noesis.interfaces.actuation import GovernedActRequest
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode
from noesis.runtime.actuation_registry import get_actuation_registry
from noesis.runtime.paths import resolve_noesis_paths


class _StaticConfig(ConfigPort):
    __api_version__ = "config/1.0-rc1"

    def __init__(self, snapshot: ConfigSnapshot) -> None:
        self._snapshot = snapshot

    def get(self) -> ConfigSnapshot:
        return self._snapshot

    def set(self, **overrides: object) -> ConfigSnapshot:
        raise NotImplementedError

    def reload(self) -> ConfigSnapshot:
        return self._snapshot


def _build_snapshot(runs_dir: Path, intuition_mode: IntuitionMode) -> ConfigSnapshot:
    return ConfigSnapshot(
        runs_dir=runs_dir,
        agents="",
        tasks="",
        timeout_sec=30,
        intuition_mode=intuition_mode,
        direction_min_confidence=0.0,
        planner_mode=PlannerMode.META,
        policy_aliases={},
        learn_mode=LearnMode.OFF,
        learn_home=runs_dir,
        learn_auto_apply_min_successes=0,
        learn_auto_apply_min_confidence=0.0,
        prompt_provenance_enabled=False,
        prompt_provenance_mode="hash_only",
        governance_mode=GovernanceMode.OFF,
        governance_failure_policy=GovernanceFailurePolicy.FAIL_OPEN,
        governance_timeout_ms=None,
        governance_pause_on_veto=False,
    )


def _find_episode_dir(root: Path) -> Path:
    layout = resolve_noesis_paths(workspace=None, runs_dir=root)
    candidates = []
    for base in layout.episode_roots():
        if not base.exists():
            continue
        candidates.extend(
            path for path in base.iterdir() if path.is_dir() and path.name.startswith("ep_")
        )
    if not candidates:
        raise AssertionError("no episode directories found")
    return candidates[0]


def test_governed_act_terminal_runs_seal_per_adr014(tmp_path: Path) -> None:
    intuition_mode = IntuitionMode.INTERVENTIVE
    snapshot = _build_snapshot(tmp_path, intuition_mode)
    context = create_runtime_context(config_port=_StaticConfig(snapshot))

    registry = get_actuation_registry()
    previous_shell = registry.shell_executor
    registry.shell_executor = lambda **_: "ok"
    try:
        result = governed_act_impl(
            request=GovernedActRequest(
                goal="touch file",
                kind="shell",
                payload={},
                seed=0,
                tags=None,
                provenance=None,
                risk_tags=None,
                redaction=None,
                determinism=None,
            ),
            context=context,
        )
    finally:
        registry.shell_executor = previous_shell

    assert result == "ok"

    run_dir = _find_episode_dir(tmp_path)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    episode = state.get("episode", {})
    assert episode.get("intuition_mode") == intuition_mode.value
    assert (run_dir / "final.json").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert any(entry.get("name") == "final.json" for entry in manifest.get("files", []))

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary.get("outcome") == "success_unverified"

    terminate_events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    terminate_payload = next(
        (event.get("payload") for event in terminate_events if event.get("phase") == "terminate"),
        None,
    )
    assert isinstance(terminate_payload, dict)
    assert terminate_payload.get("status") == "ok"


def test_governed_act_impl_delegates_to_core_governed_act(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _build_snapshot(tmp_path, IntuitionMode.INTERVENTIVE)
    context = create_runtime_context(config_port=_StaticConfig(snapshot))
    request = GovernedActRequest(
        goal="touch file",
        kind="shell",
        payload={"command": "echo ok"},
        seed=7,
        tags={"source": "test"},
        provenance={"trace": "delegation"},
        risk_tags=("safe",),
        redaction={"mode": "hash_only"},
        determinism=None,
    )
    calls: list[dict[str, Any]] = []

    def fake_governed_act(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return "delegated"

    monkeypatch.setattr(core, "governed_act", fake_governed_act)

    result = governed_act_impl(request=request, context=context)
    port_result = DefaultActuationPort().governed_act(request, context=context)

    assert result == "delegated"
    assert port_result == "delegated"
    assert len(calls) == 2
    call = calls[0]
    assert call["goal"] == request.goal
    assert call["kind"] == request.kind
    assert call["payload"] == dict(request.payload)
    assert call["context"] is context
    assert call["tags"] == dict(request.tags or {})
    assert call["provenance"] == dict(request.provenance or {})
    assert call["risk_tags"] == tuple(request.risk_tags or ())
    assert call["redaction"] == dict(request.redaction or {})


def test_governed_act_impl_does_not_write_artifacts_when_core_entry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _build_snapshot(tmp_path, IntuitionMode.INTERVENTIVE)
    context = create_runtime_context(config_port=_StaticConfig(snapshot))

    def fail_before_runtime(**_: Any) -> Any:
        raise RuntimeError("boom-before-runtime")

    monkeypatch.setattr(core, "governed_act", fail_before_runtime)

    with pytest.raises(RuntimeError, match="boom-before-runtime"):
        governed_act_impl(
            request=GovernedActRequest(
                goal="touch file",
                kind="shell",
                payload={"command": "echo ok"},
                seed=0,
                tags=None,
                provenance=None,
                risk_tags=None,
                redaction=None,
                determinism=None,
            ),
            context=context,
        )

    layout = resolve_noesis_paths(workspace=None, runs_dir=tmp_path)
    episodes_dir = layout.episodes_dir
    created = list(episodes_dir.iterdir()) if episodes_dir.exists() else []
    assert created == []
