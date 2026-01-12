from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Iterable, Sequence

from noesis.verification import (
    VerifySpec,
    file_contains,
    file_exists,
    no_modifications,
    normalize_verify,
    only_modified,
)


def load_verify_specs(path: Path) -> list[VerifySpec]:
    """Load verification specs from a JSON file."""
    if not path.exists():
        raise ValueError(f"verify file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("verify file must be a JSON list of verification specs")
    return [_parse_verify_spec(item) for item in payload]


def compile_verify_input(
    *,
    verify_file: str | None,
    verify_file_exists: Sequence[str] | None,
    verify_file_contains: Sequence[str] | None,
    verify_texts: Sequence[str] | None,
    verify_only_modified: Sequence[str] | None,
    verify_no_modifications: bool,
) -> tuple[VerifySpec, ...] | None:
    """Compile verification specs from CLI inputs."""
    specs: list[VerifySpec] = []
    if verify_file:
        specs.extend(load_verify_specs(Path(verify_file).expanduser()))
    specs.extend(
        _compile_flag_specs(
            verify_file_exists=verify_file_exists,
            verify_file_contains=verify_file_contains,
            verify_texts=verify_texts,
            verify_only_modified=verify_only_modified,
            verify_no_modifications=verify_no_modifications,
        )
    )
    if not specs:
        return None
    return normalize_verify(specs)


def _compile_flag_specs(
    *,
    verify_file_exists: Sequence[str] | None,
    verify_file_contains: Sequence[str] | None,
    verify_texts: Sequence[str] | None,
    verify_only_modified: Sequence[str] | None,
    verify_no_modifications: bool,
) -> list[VerifySpec]:
    specs: list[VerifySpec] = []
    if verify_no_modifications and verify_only_modified:
        raise ValueError("--verify-no-modifications cannot be combined with --verify-only-modified")

    for path in verify_file_exists or []:
        specs.append(file_exists(path))

    file_contains_paths = list(verify_file_contains or [])
    file_contains_texts = list(verify_texts or [])
    if file_contains_texts and not file_contains_paths:
        raise ValueError("--text requires --verify-file-contains")
    if len(file_contains_paths) != len(file_contains_texts):
        raise ValueError("each --verify-file-contains must have a matching --text")
    for path, text in zip(file_contains_paths, file_contains_texts):
        specs.append(file_contains(path, text))

    only_modified_paths = list(verify_only_modified or [])
    if only_modified_paths:
        specs.append(only_modified(only_modified_paths))

    if verify_no_modifications:
        specs.append(no_modifications())

    return specs


def _parse_verify_spec(raw: Any) -> VerifySpec:
    if not isinstance(raw, dict):
        raise ValueError("verify specs must be JSON objects")
    name = raw.get("name") or raw.get("type") or raw.get("kind")
    if not isinstance(name, str) or not name:
        raise ValueError("verify spec requires a 'name' field")
    normalized = name.strip().lower()
    if normalized == "file_exists":
        path = _require_string(raw, ("path", "target"))
        return file_exists(path)
    if normalized == "file_contains":
        path = _require_string(raw, ("path", "target"))
        text = _require_string(raw, ("text", "content"))
        return file_contains(path, text)
    if normalized == "only_modified":
        paths = _require_sequence(raw, ("paths", "target"))
        return only_modified(paths)
    if normalized == "no_modifications":
        return no_modifications()
    raise ValueError(f"unknown verify spec: {normalized}")


def _require_string(raw: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError(f"verify spec missing required field: {', '.join(keys)}")


def _require_sequence(raw: dict[str, Any], keys: Iterable[str]) -> Sequence[str]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value:
            return [value]
        if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            return value
    raise ValueError(f"verify spec missing required field: {', '.join(keys)}")
