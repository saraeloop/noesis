from __future__ import annotations

import json

import pytest

from noesis.cli.verification_input import compile_verify_input, load_verify_specs


def test_load_verify_specs_json(tmp_path) -> None:
    payload = [
        {"name": "file_exists", "path": "config.yaml"},
        {"name": "file_contains", "path": "config.yaml", "text": "enabled: true"},
        {"name": "only_modified", "paths": ["config.yaml", "README.md"]},
        {"name": "no_modifications"},
    ]
    path = tmp_path / "verify.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    specs = load_verify_specs(path)
    names = [spec.name for spec in specs]
    assert names == ["file_exists", "file_contains", "only_modified", "no_modifications"]


def test_compile_verify_input_flags() -> None:
    specs = compile_verify_input(
        verify_file=None,
        verify_file_exists=["config.yaml", "README.md"],
        verify_file_contains=["config.yaml", "README.md"],
        verify_texts=["enabled: true", "usage"],
        verify_only_modified=["config.yaml", "README.md"],
        verify_no_modifications=False,
    )
    assert specs is not None
    names = [spec.name for spec in specs]
    assert names == [
        "file_exists",
        "file_exists",
        "file_contains",
        "file_contains",
        "only_modified",
    ]


def test_compile_verify_input_requires_text() -> None:
    with pytest.raises(ValueError, match="--text"):
        compile_verify_input(
            verify_file=None,
            verify_file_exists=None,
            verify_file_contains=["README.md"],
            verify_texts=None,
            verify_only_modified=None,
            verify_no_modifications=False,
        )


def test_compile_verify_input_conflicts() -> None:
    with pytest.raises(ValueError, match="verify-no-modifications"):
        compile_verify_input(
            verify_file=None,
            verify_file_exists=None,
            verify_file_contains=None,
            verify_texts=None,
            verify_only_modified=["config.yaml"],
            verify_no_modifications=True,
        )
