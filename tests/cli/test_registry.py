"""Tests for the unified command registry invariants."""
from __future__ import annotations

import pytest

from noesis.cli.registry import (
    REGISTRY,
    COMMANDS,
    GROUP_ORDER,
    get_specs_by_group,
    get_home_specs,
    get_all_groups,
)


class TestRegistryInvariants:
    """Invariant tests to prevent registry drift."""

    def test_registry_keys_match_command_names(self):
        """Registry key must match the command's name attribute."""
        for name, spec in REGISTRY.items():
            assert spec.cmd.name == name, (
                f"Registry key '{name}' does not match cmd.name '{spec.cmd.name}'"
            )

    def test_commands_dict_matches_registry(self):
        """COMMANDS backward-compat dict must have same keys as REGISTRY."""
        assert set(COMMANDS.keys()) == set(REGISTRY.keys())

    def test_commands_dict_references_same_objects(self):
        """COMMANDS[name] must be the same object as REGISTRY[name].cmd."""
        for name, spec in REGISTRY.items():
            assert COMMANDS[name] is spec.cmd

    def test_all_groups_are_valid(self):
        """Every command must have a valid group from GROUP_ORDER."""
        valid_groups = set(GROUP_ORDER)
        for name, spec in REGISTRY.items():
            assert spec.meta.group in valid_groups, (
                f"Command '{name}' has invalid group: {spec.meta.group}"
            )

    def test_home_commands_have_examples(self):
        """Commands flagged show_on_home must have at least one example."""
        for name, spec in REGISTRY.items():
            if spec.meta.show_on_home:
                assert spec.meta.examples, (
                    f"Command '{name}' has show_on_home=True but no examples"
                )

    def test_all_commands_have_one_liner(self):
        """Every command must have a non-empty one_liner."""
        for name, spec in REGISTRY.items():
            assert spec.meta.one_liner, (
                f"Command '{name}' has empty one_liner"
            )


class TestQueryHelpers:
    """Tests for registry query functions."""

    def test_get_specs_by_group_returns_correct_commands(self):
        """get_specs_by_group returns only commands from that group."""
        for group in GROUP_ORDER:
            specs = get_specs_by_group(group)
            for spec in specs:
                assert spec.meta.group == group

    def test_get_specs_by_group_covers_all_commands(self):
        """Every command is returned by exactly one group query."""
        all_names = set()
        for group in GROUP_ORDER:
            specs = get_specs_by_group(group)
            for spec in specs:
                name = spec.cmd.name
                assert name not in all_names, f"Command '{name}' in multiple groups"
                all_names.add(name)

        assert all_names == set(REGISTRY.keys())

    def test_get_home_specs_returns_flagged_commands(self):
        """get_home_specs returns only commands with show_on_home=True."""
        home_specs = get_home_specs()
        for spec in home_specs:
            assert spec.meta.show_on_home is True

    def test_get_home_specs_matches_filter(self):
        """get_home_specs matches manual filtering."""
        expected = [spec for spec in REGISTRY.values() if spec.meta.show_on_home]
        actual = get_home_specs()
        assert set(s.cmd.name for s in actual) == set(s.cmd.name for s in expected)

    def test_get_all_groups_returns_group_order(self):
        """get_all_groups returns the canonical GROUP_ORDER."""
        assert get_all_groups() == GROUP_ORDER

    def test_group_order_has_four_groups(self):
        """GROUP_ORDER has exactly 4 groups."""
        assert len(GROUP_ORDER) == 4
        assert set(GROUP_ORDER) == {"execute", "observe", "verify", "maintain"}
