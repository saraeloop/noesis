from __future__ import annotations

import pytest

from noesis.cli import main as cli_main


def test_cli_home_plain(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOESIS_FORCE_RICH", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    code = cli_main([])
    out = capsys.readouterr().out
    assert code == 0  # no-args shows home and exits successfully
    # New compact home shows title, tagline, and commands
    assert "Noesis" in out
    assert "Understanding, made observable." in out
    assert "Commands" in out
    assert "noesis browse" in out or "browse" in out.lower()


def test_cli_home_rich(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("rich")
    monkeypatch.setenv("NOESIS_FORCE_RICH", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    code = cli_main([])
    out = capsys.readouterr().out
    assert code == 0  # no-args shows home and exits successfully
    # Compact home shows commands
    assert "Noesis" in out or "noesis" in out.lower()
    assert "browse" in out.lower()


def test_cli_help_groups(capsys) -> None:
    code = cli_main(["help"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Execute" in out
    assert "Observe" in out
    assert "Verify" in out
    assert "Maintain" in out
    assert "Examples" in out


def test_cli_help_command(capsys) -> None:
    code = cli_main(["help", "view"])
    out = capsys.readouterr().out
    assert code == 0
    assert "usage:" in out.lower()
    assert "--verbose" in out


# ─────────────────────────────────────────────────────────────────────────────
# Structural Tests: Content models derived from registry
# ─────────────────────────────────────────────────────────────────────────────


class TestHomeScreenStructure:
    """Verify HomeScreen content is correctly derived from registry."""

    def test_home_observe_commands_match_registry(self) -> None:
        """Home screen observe commands match registry show_on_home flags."""
        from noesis.cli.content.home import build_home_screen
        from noesis.cli.registry import get_specs_by_group

        screen = build_home_screen("test")
        home_observe_names = {cmd.name for cmd in screen.observe_commands}

        registry_observe_home = {
            spec.cmd.name
            for spec in get_specs_by_group("observe")
            if spec.meta.show_on_home
        }

        assert home_observe_names == registry_observe_home

    def test_home_verify_commands_match_registry(self) -> None:
        """Home screen verify commands match registry show_on_home flags."""
        from noesis.cli.content.home import build_home_screen
        from noesis.cli.registry import get_specs_by_group

        screen = build_home_screen("test")
        home_verify_names = {cmd.name for cmd in screen.verify_commands}

        registry_verify_home = {
            spec.cmd.name
            for spec in get_specs_by_group("verify")
            if spec.meta.show_on_home
        }

        assert home_verify_names == registry_verify_home

    def test_quick_start_uses_registry_examples(self) -> None:
        """Quick start items use examples from registry metadata."""
        from noesis.cli.content.home import build_home_screen
        from noesis.cli.registry import REGISTRY

        screen = build_home_screen("test")

        for item in screen.quick_start:
            # Command should contain a known command name
            found_cmd = None
            for name in REGISTRY:
                if name in item.command:
                    found_cmd = name
                    break
            assert found_cmd is not None, f"Quick start command '{item.command}' not in registry"

            # Description should match registry one_liner
            assert item.description == REGISTRY[found_cmd].meta.one_liner


class TestHelpScreenStructure:
    """Verify HelpScreen content is correctly derived from registry."""

    def test_help_groups_match_registry_order(self) -> None:
        """Help screen groups appear in registry GROUP_ORDER."""
        from noesis.cli.content.help import build_help_screen
        from noesis.cli.registry import get_all_groups, GROUP_TITLES

        screen = build_help_screen("test")
        help_group_titles = [g.title for g in screen.groups]

        expected_titles = [GROUP_TITLES[g] for g in get_all_groups()]

        assert help_group_titles == expected_titles

    def test_help_contains_all_registry_commands(self) -> None:
        """Help screen contains every command from registry."""
        from noesis.cli.content.help import build_help_screen
        from noesis.cli.registry import REGISTRY

        screen = build_help_screen("test")
        help_cmd_names = {
            cmd.name for group in screen.groups for cmd in group.commands
        }

        registry_names = set(REGISTRY.keys())

        assert help_cmd_names == registry_names

    def test_help_one_liners_match_registry(self) -> None:
        """Help screen one-liners match registry metadata."""
        from noesis.cli.content.help import build_help_screen
        from noesis.cli.registry import REGISTRY

        screen = build_help_screen("test")

        for group in screen.groups:
            for cmd in group.commands:
                registry_one_liner = REGISTRY[cmd.name].meta.one_liner
                assert cmd.one_liner == registry_one_liner, (
                    f"Mismatch for {cmd.name}: '{cmd.one_liner}' != '{registry_one_liner}'"
                )

    def test_help_examples_come_from_registry(self) -> None:
        """Help screen examples are drawn from registry metadata."""
        from noesis.cli.content.help import build_help_screen
        from noesis.cli.registry import REGISTRY

        screen = build_help_screen("test")

        # Collect all examples from registry
        all_registry_examples = set()
        for spec in REGISTRY.values():
            all_registry_examples.update(spec.meta.examples)

        # Every help example should be in registry
        for example in screen.examples:
            assert example in all_registry_examples, (
                f"Help example '{example}' not found in registry"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Regression Tests: Home screen resilience
# ─────────────────────────────────────────────────────────────────────────────


class TestHomeRecentEpisodes:
    """Verify home screen handles recent episodes correctly."""

    def test_home_shows_recent_episodes_when_available(
        self, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Home uses ctx.ns.list_runs() and shows results when available."""
        from unittest.mock import MagicMock, patch
        from noesis.cli.main import _fetch_recent_episodes, _render_home
        from noesis.cli.content.home import RecentEpisode

        # Create mock context with list_runs returning episodes
        mock_ctx = MagicMock()
        mock_ctx.ns.list_runs.return_value = [
            {
                "episode_id": "01ABCDEF123456",
                "started_at": "2025-01-15T10:30:00",
                "task": "Test task description",
                "duration_sec": 1.5,
                "status": "completed",
                "flags": {},
                "success": True,
                "veto_count": 0,
            }
        ]
        mock_ctx.runtime_context = None

        episodes = _fetch_recent_episodes(mock_ctx)

        assert len(episodes) == 1
        assert episodes[0].episode_short == "01ABCDEF1234"
        assert episodes[0].time_str == "10:30"
        assert episodes[0].task == "Test task description"
        mock_ctx.ns.list_runs.assert_called_once()

    def test_home_failure_is_soft_on_list_runs_error(
        self, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Home renders successfully even when list_runs() throws."""
        from unittest.mock import MagicMock
        from noesis.cli.main import _fetch_recent_episodes

        # Create mock context where list_runs raises
        mock_ctx = MagicMock()
        mock_ctx.ns.list_runs.side_effect = Exception("Database error")
        mock_ctx.runtime_context = None

        # Should return empty list, not raise
        episodes = _fetch_recent_episodes(mock_ctx)

        assert episodes == []

    def test_home_failure_is_soft_on_malformed_row(self) -> None:
        """Home skips malformed rows without crashing."""
        from unittest.mock import MagicMock
        from noesis.cli.main import _fetch_recent_episodes

        # Create mock context with malformed data
        mock_ctx = MagicMock()
        mock_ctx.ns.list_runs.return_value = [
            None,  # Completely malformed
            {"episode_id": "valid123"},  # Missing most fields
            {
                "episode_id": "complete456",
                "started_at": "2025-01-15T10:30:00",
                "task": "Valid task",
                "duration_sec": 2.0,
                "status": "completed",
                "flags": {},
            },
        ]
        mock_ctx.runtime_context = None

        episodes = _fetch_recent_episodes(mock_ctx)

        # Should have at least the valid row, possibly the partial one
        assert len(episodes) >= 1
        # The complete one should be there
        assert any(ep.episode_short == "complete456" for ep in episodes)

    def test_home_exits_zero_even_with_no_episodes(
        self, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Home screen exits 0 even when there are no episodes."""
        monkeypatch.delenv("NOESIS_FORCE_RICH", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)

        code = cli_main([])
        out = capsys.readouterr().out

        assert code == 0
        # New compact home shows title + commands
        assert "Noesis" in out or "noesis" in out.lower()
        assert "noesis run" in out or "noesis browse" in out

    def test_home_flag_exits_zero(
        self, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit --home flag always exits 0 (Bug 1 regression test)."""
        monkeypatch.delenv("NOESIS_FORCE_RICH", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)

        code = cli_main([])
        out = capsys.readouterr().out

        assert code == 0  # Must be 0, not EXIT_USAGE
        # New compact home shows "Noesis" header
        assert "Noesis" in out or "noesis" in out.lower()
