"""Contract tests for ADR-012: CLI Observe Boundary Contract (cli/1.1)."""
from __future__ import annotations

import json
from contextlib import contextmanager

import noesis as ns
from noesis.cli import main as cli_main


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def test_view_json_envelope(tmp_path, capsys) -> None:
    """Test that view --json emits ViewResult envelope per ADR-012."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # First create an episode
        run_code = cli_main(["run", "view contract test", "--json"])
        capsys.readouterr()  # Clear run output
        assert run_code == 0

        # Get the episode ID from the runs directory
        episode_dirs = list(runs_dir.glob("ep_*"))
        assert len(episode_dirs) == 1
        episode_id = episode_dirs[0].name

        # Now test view --json
        view_code = cli_main(["view", episode_id, "--json"])
        captured = capsys.readouterr()

        assert view_code == 0
        assert captured.err == ""

        # Parse envelope
        lines = captured.out.strip().splitlines()
        assert len(lines) == 1
        envelope = json.loads(lines[0])

        # Verify cli block (ADR-012)
        cli = envelope["cli"]
        assert cli["schema_version"] == "cli/1.1"
        assert cli["compat_min"] == "cli/1.0"
        assert cli["compat_max"] == "cli/1.x"

        # Verify required fields
        assert envelope["episode_id"] == episode_id
        assert "episode_dir" in envelope
        assert "artifacts" in envelope
        assert "dashboard" in envelope

        # Verify dashboard structure
        dashboard = envelope["dashboard"]
        assert "header" in dashboard
        assert "chips" in dashboard
        assert "kpis" in dashboard
        assert "timeline_rows" in dashboard


def test_ps_json_envelope(tmp_path, capsys) -> None:
    """Test that ps --json emits PsResult envelope."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # Create a couple episodes under the same process
        cli_main(["run", "ps test 1", "--json"])
        cli_main(["run", "ps test 2", "--json"])
        capsys.readouterr()  # Clear run output

        # Test ps --json
        ps_code = cli_main(["ps", "--json", "--limit", "10"])
        captured = capsys.readouterr()

        assert ps_code == 0
        assert captured.err == ""

        # Parse envelope
        lines = captured.out.strip().splitlines()
        assert len(lines) == 1
        envelope = json.loads(lines[0])

        # Verify cli block (ADR-012)
        cli = envelope["cli"]
        assert cli["schema_version"] == "cli/1.1"
        assert cli["compat_min"] == "cli/1.0"
        assert cli["compat_max"] == "cli/1.x"

        # Verify required fields
        assert "processes" in envelope
        assert isinstance(envelope["processes"], list)
        assert len(envelope["processes"]) >= 1
        assert envelope["limit"] == 10
        assert envelope["total_count"] >= 1
        assert "offset" in envelope

        # Verify process row structure
        process = envelope["processes"][0]
        assert "process_id" in process
        assert "process_name" in process
        assert "kind" in process
        assert "status" in process
        assert "last_seen_at" in process


def test_events_json_envelope(tmp_path, capsys) -> None:
    """Test that events --envelope emits EventsResult envelope per ADR-012."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # Create an episode
        cli_main(["run", "events contract test", "--json"])
        capsys.readouterr()

        # Get episode ID
        episode_dirs = list(runs_dir.glob("ep_*"))
        assert len(episode_dirs) == 1
        episode_id = episode_dirs[0].name

        # Test events --envelope
        events_code = cli_main(["events", episode_id, "--envelope"])
        captured = capsys.readouterr()

        assert events_code == 0
        assert captured.err == ""

        # Parse envelope
        lines = captured.out.strip().splitlines()
        assert len(lines) == 1
        envelope = json.loads(lines[0])

        # Verify cli block (ADR-012)
        cli = envelope["cli"]
        assert cli["schema_version"] == "cli/1.1"
        assert cli["compat_min"] == "cli/1.0"
        assert cli["compat_max"] == "cli/1.x"

        # Verify required fields
        assert envelope["episode_id"] == episode_id
        assert "events" in envelope
        assert isinstance(envelope["events"], list)
        assert "filters" in envelope
        assert "event_count" in envelope
        assert envelope["event_count"] == len(envelope["events"])


def test_events_json_streaming_preserved(tmp_path, capsys) -> None:
    """Test that events --json still emits JSONL streaming (backward compat)."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # Create an episode
        cli_main(["run", "events streaming test", "--json"])
        capsys.readouterr()

        # Get episode ID
        episode_dirs = list(runs_dir.glob("ep_*"))
        episode_id = episode_dirs[0].name

        # Test events --json (JSONL mode)
        events_code = cli_main(["events", episode_id, "--json"])
        captured = capsys.readouterr()

        assert events_code == 0

        # Each line should be a valid JSON object (JSONL)
        lines = captured.out.strip().splitlines()
        assert len(lines) >= 1

        for line in lines:
            event = json.loads(line)
            # JSONL events don't have cli block
            assert "cli" not in event
            # They have event-specific fields
            assert "phase" in event or "episode_id" in event


def test_events_envelope_with_phase_filter(tmp_path, capsys) -> None:
    """Test that events --envelope respects --phase filter."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # Create an episode
        cli_main(["run", "events filter test", "--json"])
        capsys.readouterr()

        episode_dirs = list(runs_dir.glob("ep_*"))
        episode_id = episode_dirs[0].name

        # Test events --envelope --phase start
        events_code = cli_main(["events", episode_id, "--envelope", "--phase", "start"])
        captured = capsys.readouterr()

        assert events_code == 0
        envelope = json.loads(captured.out.strip())

        # Verify filter is recorded
        assert envelope["filters"]["phase"] == "start"

        # Verify only start events (if any)
        for event in envelope["events"]:
            assert event.get("phase") == "start"


def test_observe_cli_version_compat(tmp_path, capsys) -> None:
    """Test that observe commands emit compatible cli version."""
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        # Test ps --json version compatibility
        ps_code = cli_main(["ps", "--json"])
        captured = capsys.readouterr()

        envelope = json.loads(captured.out.strip())
        cli = envelope["cli"]

        # cli/1.1 is compatible with cli/1.0 consumers
        assert cli["compat_min"] == "cli/1.0"
        assert cli["compat_max"].startswith("cli/1.")
