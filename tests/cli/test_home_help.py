from __future__ import annotations

import pytest

from noesis import cli


def test_cli_home_plain(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOESIS_FORCE_RICH", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    code = cli.main([])
    out = capsys.readouterr().out
    assert code == 0  # no-args shows home and exits successfully
    assert "Noēsis" in out
    assert "Quick Start" in out
    assert "Observe" in out
    assert "Verify" in out


def test_cli_home_rich(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("rich")
    monkeypatch.setenv("NOESIS_FORCE_RICH", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    code = cli.main([])
    out = capsys.readouterr().out
    assert code == 0  # no-args shows home and exits successfully
    assert "Quick Start" in out


def test_cli_help_groups(capsys) -> None:
    code = cli.main(["help"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Execute" in out
    assert "Observe" in out
    assert "Verify" in out
    assert "Maintain" in out
    assert "Examples" in out


def test_cli_help_command(capsys) -> None:
    code = cli.main(["help", "view"])
    out = capsys.readouterr().out
    assert code == 0
    assert "usage:" in out.lower()
    assert "--events" in out


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
