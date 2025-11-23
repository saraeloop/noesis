from __future__ import annotations

from pathlib import Path
from typing import Literal

from noesis.infrastructure.state_repository import EpisodeContext
from noesis.runtime.prompt_recorder import PromptRecorder


Mode = Literal["full", "hash_only"]


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
    recorder.record(phase="plan")


def test_prompt_recorder_enabled_full_mode(tmp_path: Path) -> None:
    recorder = PromptRecorder.from_context(_context(tmp_path, enabled=True, mode="full"))
    assert recorder.is_enabled() is True
    assert recorder.mode == "full"

