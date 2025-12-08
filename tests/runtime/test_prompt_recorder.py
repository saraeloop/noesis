from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from noesis.infrastructure.state_repository import EpisodeContext
from noesis.runtime.prompt_recorder import PromptRecorder


Mode = Literal["full", "hash_only", "redacted"]


def _context(tmp_path: Path, *, enabled: bool, mode: Mode) -> EpisodeContext:
    return EpisodeContext(
        run_dir=tmp_path,
        episode_id="ep_test",
        seed=0,
        task="demo",
        tags={},
        adapter_label="adapter:core",
        started_at="2025-01-01T00:00:00Z",
        prompt_provenance_enabled=enabled,
        prompt_provenance_mode=mode,
    )


def test_prompt_recorder_disabled(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=False, mode="hash_only"))
    assert recorder.is_enabled() is False
    assert recorder.mode == "hash_only"
    # The skeleton no-ops even when invoked.
    recorder.record(phase="plan", agent_id="planner.test", rendered="ignored")


def test_prompt_recorder_enabled_full_mode(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=True, mode="full"))
    assert recorder.is_enabled() is True
    assert recorder.mode == "full"


def test_prompt_recorder_writes_prompts_file(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=True, mode="full"))
    recorder.record(
        phase="plan",
        agent_id="planner.test",
        rendered="demo prompt",
        template="demo {{x}}",
        variables={"x": 1},
        tags={"env": "demo"},
    )

    path = tmp_path / "prompts.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["rendered"] == "demo prompt"
    assert payload["template"] == "demo {{x}}"
    assert payload["variables"] == {"x": 1}
    assert payload["tags"] == {"env": "demo"}
    assert payload["fingerprint"].startswith("sha256:")
    assert payload["episode_id"] == "ep_test"
    assert payload["phase"] == "plan"


def test_prompt_recorder_hash_only_omits_rendered(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=True, mode="hash_only"))
    recorder.record(
        phase="plan",
        agent_id="planner.test",
        rendered="demo prompt",
        template="demo {{x}}",
        variables={"x": 1},
        tags={"env": "demo"},
    )

    data = (tmp_path / "prompts.jsonl").read_text(encoding="utf-8").splitlines()
    assert data, "prompts.jsonl should contain a record"
    payload = json.loads(data[0])
    assert "rendered" not in payload
    assert "template" not in payload
    assert "variables" not in payload
    assert payload["mode"] == "hash_only"
    assert payload["fingerprint"].startswith("sha256:")


def test_prompt_recorder_redacts_content(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=True, mode="redacted"))
    recorder.record(
        phase="plan",
        agent_id="planner.test",
        rendered="secret",
        template="demo {{secret}}",
        variables={"secret": "top"},
    )

    payload = json.loads((tmp_path / "prompts.jsonl").read_text(encoding="utf-8").strip())
    assert payload["rendered"] == "__redacted__"
    assert payload["template"] == "__redacted__"
    assert "variables" not in payload
    assert payload["fingerprint"].startswith("sha256:")
