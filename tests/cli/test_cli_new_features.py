"""Tests for new CLI features: home screen, explain command, and governance summary."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from noesis.cli import main as cli_main
from noesis.cli.content.home import (
    build_home_screen,
    ConfigSnapshot,
    LastEpisodeInfo,
    RecentEpisode,
)
from noesis.cli.commands.explain import _build_explain_vm, ExplainVM
from noesis.cli.view_models import build_episode_dashboard, GovernanceSummaryVM


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def golden_veto_dir() -> Path:
    """Path to golden veto_enforce fixtures."""
    return Path(__file__).parent.parent / "golden" / "veto_enforce" / "run_a" / "ep_01JGVETO00000000000000000"


@pytest.fixture
def veto_summary(golden_veto_dir: Path) -> dict:
    """Load golden veto summary."""
    return json.loads((golden_veto_dir / "summary.json").read_text())


@pytest.fixture
def veto_events(golden_veto_dir: Path) -> list[dict]:
    """Load golden veto events."""
    events = []
    with open(golden_veto_dir / "events.jsonl") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


# ─────────────────────────────────────────────────────────────────────────────
# HOME SCREEN TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_build_home_screen_basic():
    """Home screen builds without crashing with minimal input."""
    screen = build_home_screen("1.0.0")
    assert screen.version == "1.0.0"
    assert screen.tagline == "Understanding, made observable."
    assert screen.config.governance_mode == "off"
    assert screen.config.planner_mode == "minimal"
    assert len(screen.next_actions) > 0


def test_build_home_screen_with_config():
    """Home screen includes config snapshot when provided."""
    screen = build_home_screen(
        "1.0.0",
        config_snapshot={
            "governance_mode": "enforce",
            "planner_mode": "meta",
            "intuition_mode": "required",
            "runs_dir": "/custom/runs",
        },
    )
    assert screen.config.governance_mode == "enforce"
    assert screen.config.planner_mode == "meta"
    assert screen.config.intuition_mode == "required"
    assert screen.config.runs_dir == "/custom/runs"


def test_build_home_screen_with_vetoed_episode():
    """Home screen shows veto-specific next actions for vetoed episodes."""
    last_episode = LastEpisodeInfo(
        episode_id="ep_test",
        status="VETOED",
        duration="0.1s",
        task="Bad task",
        rule_id="rules.veto.test",
        score=0.95,
        message="Blocked by policy",
    )
    screen = build_home_screen(
        "1.0.0",
        last_episode_info=last_episode,
    )
    assert screen.last_episode is not None
    assert screen.last_episode.status == "VETOED"
    # Should suggest explain for vetoed episodes
    commands = [a.command for a in screen.next_actions]
    assert any("explain" in cmd for cmd in commands)


def test_build_home_screen_with_recent_episodes():
    """Home screen displays recent episodes."""
    recent = [
        RecentEpisode(
            time_str="10:30",
            episode_short="ep_abc123",
            episode_id="ep_abc123456789",
            status="SUCCESS",
            task="Test task",
            duration="0.5s",
        ),
    ]
    screen = build_home_screen("1.0.0", recent_episodes=recent)
    assert len(screen.recent_episodes) == 1
    assert screen.recent_episodes[0].episode_short == "ep_abc123"


# ─────────────────────────────────────────────────────────────────────────────
# EXPLAIN COMMAND TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_explain_vm_from_veto_events(veto_summary, veto_events):
    """Explain VM extracts governance details from vetoed episode."""
    vm = _build_explain_vm("ep_01JGVETO00000000000000000", veto_summary, veto_events)

    assert vm.episode_id == "ep_01JGVETO00000000000000000"
    assert vm.status == "vetoed"
    assert vm.governance is not None
    # Decision is stored as-is from payload (lowercase)
    assert vm.governance.decision.lower() == "veto"
    assert vm.governance.enforced is True
    assert vm.governance.rule_id == "rule:deny-act"


def test_explain_vm_direction_blocks(veto_events):
    """Explain VM extracts direction blocks."""
    vm = _build_explain_vm("test", None, veto_events)

    assert len(vm.direction_blocks) > 0
    block = vm.direction_blocks[0]
    assert block.status == "blocked"
    assert block.reason == "governance_veto"


def test_explain_vm_causal_chain(veto_events):
    """Explain VM builds causal chain from events."""
    vm = _build_explain_vm("test", None, veto_events)

    phases = [step.phase for step in vm.causal_chain]
    # Should include key phases
    assert "plan" in phases
    assert "governance" in phases
    assert "terminate" in phases


def test_explain_vm_next_actions():
    """Explain VM suggests appropriate next actions."""
    events = [
        {"phase": "governance", "payload": {"decision": "veto", "enforced": True}},
        {"phase": "terminate", "payload": {"status": "vetoed"}},
    ]
    vm = _build_explain_vm("ep_test", {"status": "vetoed"}, events)

    assert len(vm.next_actions) > 0
    # Should suggest view for vetoed episodes
    assert any("view" in action for action in vm.next_actions)


def test_explain_risky_tokens():
    """Explain VM detects risky tokens in task."""
    events = []
    vm = _build_explain_vm("test", {"task": "delete all from production database"}, events)

    assert "delete" in vm.risky_tokens
    assert "production" in vm.risky_tokens
    assert "database" in vm.risky_tokens


# ─────────────────────────────────────────────────────────────────────────────
# VIEW GOVERNANCE SUMMARY TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_view_dashboard_governance_summary(golden_veto_dir):
    """View dashboard includes governance summary for vetoed episodes."""
    if not golden_veto_dir.exists():
        pytest.skip("Golden veto fixture not found")

    vm = build_episode_dashboard(golden_veto_dir)

    assert vm.header.governance is not None
    assert vm.header.governance.decision == "VETO"
    assert vm.header.governance.enforced is True
    assert vm.header.governance.rule_id == "rule:deny-act"


def test_view_dashboard_to_dict_includes_governance(golden_veto_dir):
    """View dashboard to_dict includes governance info."""
    if not golden_veto_dir.exists():
        pytest.skip("Golden veto fixture not found")

    vm = build_episode_dashboard(golden_veto_dir)
    data = vm.to_dict()

    assert data["header"]["governance"] is not None
    assert data["header"]["governance"]["decision"] == "VETO"
    assert data["header"]["governance"]["enforced"] is True


# ─────────────────────────────────────────────────────────────────────────────
# CLI INTEGRATION TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_events_no_theme_crash(capsys):
    """noesis events should not crash with theme attribute error."""
    # This should not raise "'Console' object has no attribute 'theme'"
    code = cli_main(["events", "--help"])
    assert code == 0


def test_cli_explain_help(capsys):
    """noesis explain --help works."""
    code = cli_main(["explain", "--help"])
    out = capsys.readouterr().out
    assert code == 0
    assert "explain" in out.lower() or "episode" in out.lower()


def test_cli_home_no_args(capsys):
    """noesis (no args) renders home screen without error."""
    code = cli_main([])
    out = capsys.readouterr().out
    # Should not crash and should show something
    assert code == 0


# ─────────────────────────────────────────────────────────────────────────────
# RENDERER TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_plain_renderer_home_screen():
    """Plain renderer handles new home screen model."""
    from noesis.cli.render.plain import PlainRenderer
    from io import StringIO
    import sys

    renderer = PlainRenderer()
    screen = build_home_screen(
        "1.0.0",
        config_snapshot={"governance_mode": "enforce"},
    )

    # Capture output
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        renderer.print_home(screen)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert "Noesis" in output
    assert "Commands" in output


def test_plain_renderer_explain():
    """Plain renderer handles explain view model."""
    from noesis.cli.render.plain import PlainRenderer
    from noesis.cli.commands.explain import GovernanceDecision, ExplainVM, CausalStep
    from io import StringIO
    import sys

    renderer = PlainRenderer()
    vm = ExplainVM(
        episode_id="ep_test",
        task="Test task",
        status="vetoed",
        governance=GovernanceDecision(
            decision="veto",
            enforced=True,
            mode="enforce",
            rule_id="rules.test",
            policy_id=None,
            policy_version=None,
            score=0.95,
            message="Test blocked",
        ),
        intuition_advice=[],
        direction_blocks=[],
        risky_tokens=["test"],
        causal_chain=[CausalStep("governance", "veto")],
        next_actions=["noesis view ep_test"],
    )

    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        renderer.print_explain(vm)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert "VETOED" in output
    assert "rules.test" in output
    assert "0.95" in output
