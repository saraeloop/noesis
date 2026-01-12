"""Public verification helpers for workspace assertions."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable, Sequence, TypeAlias

from noesis.domain.verification import (
    Assertion,
    FileContainsAssertion,
    FileExistsAssertion,
    NoModificationsAssertion,
    OnlyModifiedAssertion,
)

VerifySpec: TypeAlias = Assertion
VerifyInput: TypeAlias = VerifySpec | Sequence[VerifySpec] | None

__all__ = [
    "VerifyInput",
    "VerifySpec",
    "file_contains",
    "file_exists",
    "no_modifications",
    "normalize_verify",
    "only_modified",
]


def file_exists(path: str | Path) -> VerifySpec:
    """Return a verification spec requiring a file to exist."""
    return FileExistsAssertion(path)


def file_contains(
    path: str | Path,
    pattern: str | re.Pattern[str],
    *,
    literal: bool = False,
) -> VerifySpec:
    """
    Return a verification spec requiring file content to include a pattern.

    Note: regex matching is not supported in v0.1; pass literal=True when using
    a compiled pattern to match its raw string.
    """
    if isinstance(pattern, re.Pattern):
        if not literal:
            raise ValueError("regex patterns are not supported; pass literal=True")
        text = pattern.pattern
    else:
        text = str(pattern)
    return FileContainsAssertion(path, text)


def only_modified(paths: Sequence[str | Path]) -> VerifySpec:
    """Return a verification spec restricting modifications to the given paths."""
    return OnlyModifiedAssertion(paths)


def no_modifications() -> VerifySpec:
    """Return a verification spec requiring no workspace modifications."""
    return NoModificationsAssertion()


def normalize_verify(verify: VerifyInput) -> tuple[VerifySpec, ...] | None:
    """Normalize verification input into a tuple of verification specs."""
    if verify is None:
        return None
    if _is_spec(verify):
        return (verify,)
    if isinstance(verify, Sequence) and not isinstance(verify, (str, bytes)):
        specs = tuple(verify)
        for spec in specs:
            if not _is_spec(spec):
                raise TypeError("verify must contain only verification specs")
        return specs
    raise TypeError("verify must be a verification spec or a sequence of specs")


def _is_spec(value: object) -> bool:
    return bool(getattr(value, "evaluate", None)) and bool(getattr(value, "name", None))
