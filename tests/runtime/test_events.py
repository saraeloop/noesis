from __future__ import annotations

import pytest

from noesis import events
from noesis.trace.events import EventLogIntegrityError, read_events, write_event


def test_runtime_events_smoke(tmp_path):
    run_dir = tmp_path / "episode"
    episode_id = "ep-runtime"

    events.start(run_dir, episode_id, {"task": "demo"})
    events.ensure(
        run_dir,
        episode_id,
        adapter_label="adapter.test",
        input_excerpt="demo",
        outcome="ok",
    )

    recorded = read_events(run_dir)
    phases = [evt["phase"] for evt in recorded]

    assert "start" in phases
    assert "act" in phases


def test_read_events_raises_on_corrupted_event_log(tmp_path) -> None:
    run_dir = tmp_path / "episode-corrupt"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        '\n'.join(
            [
                '{"timestamp":"2026-01-01T00:00:00Z","episode_id":"ep-corrupt","phase":"start","payload":{},"evidence_ids":[]}',
                '{"timestamp":',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EventLogIntegrityError) as exc:
        read_events(run_dir)

    corruption = exc.value.corruption
    assert corruption.path == run_dir / "events.jsonl"
    assert corruption.line_number == 2


def test_write_event_rejects_append_when_existing_log_is_corrupt(tmp_path) -> None:
    run_dir = tmp_path / "episode-append-corrupt"
    run_dir.mkdir()
    events_path = run_dir / "events.jsonl"
    original = '{"timestamp":"2026-01-01T00:00:00Z"\n'
    events_path.write_text(original, encoding="utf-8")

    with pytest.raises(EventLogIntegrityError):
        write_event(
            run_dir,
            {
                "timestamp": "2026-01-01T00:00:01Z",
                "episode_id": "ep-append-corrupt",
                "phase": "start",
                "payload": {},
                "evidence_ids": [],
            },
            validate=False,
        )

    assert events_path.read_text(encoding="utf-8") == original


def test_write_event_rejects_append_when_middle_record_is_corrupt(tmp_path) -> None:
    run_dir = tmp_path / "episode-middle-corrupt"
    run_dir.mkdir()
    events_path = run_dir / "events.jsonl"
    original = (
        '{"timestamp":"2026-01-01T00:00:00Z","episode_id":"ep-middle-corrupt","phase":"start","payload":{},"evidence_ids":[]}\n'
        '{"timestamp":\n'
        '{"timestamp":"2026-01-01T00:00:02Z","episode_id":"ep-middle-corrupt","phase":"reflect","payload":{"success":true},"evidence_ids":[]}\n'
    )
    events_path.write_text(original, encoding="utf-8")

    with pytest.raises(EventLogIntegrityError) as exc:
        write_event(
            run_dir,
            {
                "timestamp": "2026-01-01T00:00:03Z",
                "episode_id": "ep-middle-corrupt",
                "phase": "terminate",
                "payload": {"status": "ok"},
                "evidence_ids": [],
            },
            validate=False,
        )

    assert exc.value.corruption.line_number == 2
    assert events_path.read_text(encoding="utf-8") == original


def test_read_events_rejects_truncated_final_line(tmp_path) -> None:
    run_dir = tmp_path / "episode-truncated-tail"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        '{"timestamp":"2026-01-01T00:00:00Z","episode_id":"ep-truncated-tail","phase":"start","payload":{},"evidence_ids":[]}\n'
        '{"timestamp":"2026-01-01T00:00:01Z","episode_id":"ep-truncated-tail"',
        encoding="utf-8",
    )

    with pytest.raises(EventLogIntegrityError) as exc:
        read_events(run_dir)

    assert exc.value.corruption.line_number == 2


def test_read_events_rejects_invalid_utf8_in_non_tail_record(tmp_path) -> None:
    run_dir = tmp_path / "episode-invalid-utf8"
    run_dir.mkdir()
    with (run_dir / "events.jsonl").open("wb") as handle:
        handle.write(
            b'{"timestamp":"2026-01-01T00:00:00Z","episode_id":"ep-invalid-utf8","phase":"start","payload":{},"evidence_ids":[]}\n'
        )
        handle.write(b"\xff\xfe\n")
        handle.write(
            b'{"timestamp":"2026-01-01T00:00:02Z","episode_id":"ep-invalid-utf8","phase":"reflect","payload":{"success":true},"evidence_ids":[]}\n'
        )

    with pytest.raises(EventLogIntegrityError) as exc:
        read_events(run_dir)

    assert exc.value.corruption.line_number == 2
