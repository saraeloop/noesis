"""
Record a real LLM transcript and generate offline-replay goldens.

This script is for maintainers only and should not run in CI.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib import request

from noesis.domain.faculties.intuition import IntuitionMode, LLMIntuition
from noesis.domain.learning.model import LearnMode
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG
from noesis.runtime.session import SessionBuilder
from noesis.runtime.artifacts.writer import ManifestWriter

from tests.infrastructure.llm_replay import (
    ReplayLLMProvider,
    TRANSCRIPT_VERSION,
    write_transcript,
)


PROMPT_SYSTEM = "You are a JSON generator. Return only JSON."
PROMPT_USER = (
    "Return a JSON object with keys: kind, advice, confidence, rationale, target, scope, blocking. "
    "Use: kind='hint', advice='Use short sentences.', confidence=0.5, rationale='golden', "
    "target='input', scope='episode', blocking=false."
)

MODEL_DEFAULT = "gpt-4o-mini"
GOLDEN_TASK = "LLM intuition smoke test"
EPISODE_TS_MS = 1_735_700_000_000
EPISODE_SEED = 4242
TICK_MS = 5.0


class _SnapshotPort(ConfigPort):
    __api_version__ = "config/1.0-rc1"

    def __init__(self, snapshot: ConfigSnapshot) -> None:
        self._snapshot = snapshot

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


def _snapshot_for(root: Path) -> ConfigSnapshot:
    learn_home = root / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    payload: Mapping[str, object] = {
        "runs_dir": str(root),
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
        "prompt_provenance_enabled": False,
        "prompt_provenance_mode": "hash_only",
    }
    return ConfigSnapshot.from_mapping(payload)


def _build_session(root: Path) -> object:
    clock = DeterministicClock(
        start_at=datetime.fromtimestamp(EPISODE_TS_MS / 1000, tz=timezone.utc),
        tick_ms=TICK_MS,
    )
    rng = DeterministicRNG(seed=EPISODE_SEED)
    snapshot = _snapshot_for(root)
    port = _SnapshotPort(snapshot)
    builder = SessionBuilder(config_port=port).with_determinism(
        clock=clock,
        rng=rng,
        episode_timestamp_ms=EPISODE_TS_MS,
    )
    return builder.build()


def _openai_chat_completion(api_key: str, *, model: str, messages: list[dict[str, str]]) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 120,
        "messages": messages,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI response missing choices")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise RuntimeError("OpenAI response missing message content")
    return content


def _extract_json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not locate JSON object in LLM response")
    return json.loads(cleaned[start : end + 1])


def _record_transcript(model: str, transcript_path: Path) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set to record the LLM golden")
    messages = [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user", "content": PROMPT_USER},
    ]
    response_text = _openai_chat_completion(api_key, model=model, messages=messages)
    payload = _extract_json_payload(response_text)
    entry = {
        "schema_version": TRANSCRIPT_VERSION,
        "request": {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 120,
        },
        "response": {
            "content": response_text,
            "payload": payload,
        },
    }
    write_transcript(transcript_path, [entry])
    return entry


def _write_transcript_to_run(run_dir: Path, transcript_path: Path) -> None:
    target = run_dir / "transcript.jsonl"
    target.write_text(transcript_path.read_text(encoding="utf-8"), encoding="utf-8")
    ManifestWriter(run_dir=run_dir, episode_id=run_dir.name).finalize()


def _run_replay(root: Path, transcript_path: Path) -> str:
    session = _build_session(root)
    provider = ReplayLLMProvider(transcript_path)
    intuition = LLMIntuition(response_provider=provider)
    return session.run(GOLDEN_TASK, intuition=intuition, seed=EPISODE_SEED)


def _prepare_root(path: Path, *, force: bool) -> None:
    if path.exists():
        if force:
            shutil.rmtree(path)
        else:
            raise SystemExit(f"{path} already exists (use --force to overwrite)")
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a real LLM golden and generate replays.")
    parser.add_argument("--model", default=MODEL_DEFAULT, help="Model name for recording")
    parser.add_argument("--force", action="store_true", help="Overwrite existing golden runs")
    args = parser.parse_args()

    base = Path("tests/golden/llm_real")
    run_a = base / "run_a"
    run_b = base / "run_b"
    transcript_path = base / "transcript.jsonl"

    _prepare_root(run_a, force=args.force)
    _prepare_root(run_b, force=args.force)

    _record_transcript(args.model, transcript_path)

    ep_a = _run_replay(run_a, transcript_path)
    ep_b = _run_replay(run_b, transcript_path)

    _write_transcript_to_run(run_a / ep_a, transcript_path)
    _write_transcript_to_run(run_b / ep_b, transcript_path)

    print(f"Recorded transcript: {transcript_path}")
    print(f"Replay runs: {run_a / ep_a} | {run_b / ep_b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
