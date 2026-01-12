from __future__ import annotations

import re

import pytest

import noesis as ns


def test_file_exists_helper_builds_spec() -> None:
    spec = ns.file_exists("config.yaml")

    assert spec.name == "file_exists"


def test_file_contains_rejects_regex_without_literal() -> None:
    pattern = re.compile(r"enabled:\s+true")

    with pytest.raises(ValueError):
        ns.file_contains("config.yaml", pattern)


def test_file_contains_accepts_literal_regex() -> None:
    pattern = re.compile(r"enabled:\s+true")

    spec = ns.file_contains("config.yaml", pattern, literal=True)

    assert spec.name == "file_contains"


def test_normalize_verify_accepts_single_and_sequence() -> None:
    single = ns.file_exists("config.yaml")
    sequence = [ns.no_modifications()]

    assert ns.normalize_verify(single) == (single,)
    assert ns.normalize_verify(sequence) == tuple(sequence)


def test_normalize_verify_rejects_invalid() -> None:
    with pytest.raises(TypeError):
        ns.normalize_verify(["bad"])
