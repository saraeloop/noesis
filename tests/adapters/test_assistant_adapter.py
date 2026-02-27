from __future__ import annotations

import json
from pathlib import Path

import pytest

import noesis.adapters.assistant as assistant_module
from noesis.adapters.assistant import AssistantsAdapter
from noesis.domain.artifacts.immutability import ImmutabilityError
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
    result = adapter.execute(task="demo café task", episode_id="ep-1", run_dir=run_dir)

    assert result["assistant_reply"].startswith("Processed task:")
    events = _read_events(run_dir)
    assert [event["phase"] for event in events] == ["reason", "act"]
    assert all(event["agent_id"] == "adapter.assistants" for event in events)
    # Canonical serializer keeps UTF-8 characters unescaped.
    raw = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "café" in raw
    assert "\\u00e9" not in raw


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
    intuition_event = events[0]
    direction_event = events[2]
    assert intuition_event["faculty"] == "intuition"
    assert direction_event["faculty"] == "direction"


def test_assistant_adapter_respects_finalization_seal(tmp_path: Path) -> None:
    class DummyAssistant:
        pass

    adapter = AssistantsAdapter(DummyAssistant())
    run_dir = tmp_path / "sealed-episode"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "final.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ImmutabilityError):
        adapter.execute(task="should fail", episode_id="ep-sealed", run_dir=run_dir)


def test_assistant_adapter_normalizes_older_timestamps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter(
        [
            "2025-01-01T00:00:00.001000+00:00",
            "2025-01-01T00:00:00.000000+00:00",
        ]
    )
    monkeypatch.setattr(assistant_module, "_ts", lambda: next(ticks))
    run_dir = tmp_path / "episode"

    assistant_module._append_event(
        run_dir,
        episode_id="ep-time",
        phase="reason",
        agent_id="adapter.assistants",
        payload={"note": "first"},
    )
    assistant_module._append_event(
        run_dir,
        episode_id="ep-time",
        phase="reason",
        agent_id="adapter.assistants",
        payload={"note": "second"},
    )
    events = _read_events(run_dir)
    assert events[0]["timestamp"] == "2025-01-01T00:00:00.001000+00:00"
    assert events[1]["timestamp"] == "2025-01-01T00:00:00.001000+00:00"
