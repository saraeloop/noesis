from __future__ import annotations

import json
from pathlib import Path

import pytest

from noesis.adapters.assistant import AssistantsAdapter
from noesis.direction import DirectiveKind
from noesis.exceptions import NoesisVeto
from noesis.intuition import IntuitionEvent


def _read_events(path: Path) -> list[dict[str, object]]:
    events_path = path / "events.jsonl"
    assert events_path.exists()
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_assistant_adapter_writes_events_jsonl(tmp_path: Path) -> None:
    class DummyAssistant:
        pass

    adapter = AssistantsAdapter(DummyAssistant())
    run_dir = tmp_path / "episode"
    result = adapter.execute(task="demo task", episode_id="ep-1", run_dir=run_dir)

    assert result["assistant_reply"].startswith("Processed task:")
    events = _read_events(run_dir)
    assert [event["phase"] for event in events] == ["reason", "act"]
    assert all(event["agent_id"] == "adapter.assistants" for event in events)


def test_assistant_adapter_logs_veto_and_raises(tmp_path: Path) -> None:
    class DummyAssistant:
        pass

    class BlockingIntuition:
        def advise(self, state: dict[str, object]) -> IntuitionEvent | None:
            _ = state
            return IntuitionEvent(
                kind=DirectiveKind.VETO.value,
                advice="blocked",
                confidence=1.0,
                blocking=True,
            )

    adapter = AssistantsAdapter(DummyAssistant())
    run_dir = tmp_path / "episode"
    with pytest.raises(NoesisVeto):
        adapter.execute(
            task="dangerous",
            episode_id="ep-2",
            run_dir=run_dir,
            intuition=BlockingIntuition(),
        )

    events = _read_events(run_dir)
    phases = [event["phase"] for event in events]
    assert phases == ["intuition", "reason", "direction", "act", "error"]
