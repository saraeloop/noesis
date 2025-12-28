from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Styles:
    ok: str = "✅"
    warn: str = "⚠️"
    err: str = "❌"
    info: str = "ℹ️"


def headline(text: str) -> None:
    print(f"\n{text}\n" + ("-" * len(text)))


def info(msg: str) -> None:
    print(f"{Styles().info} {msg}")


def success(msg: str) -> None:
    print(f"{Styles().ok} {msg}")


def warn(msg: str) -> None:
    print(f"{Styles().warn} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"{Styles().err} {msg}", file=sys.stderr)