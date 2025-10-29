from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import sys

import noesis as ns
from noesis import config as _cfg


@dataclass
class GlobalOptions:
    compact: bool | None = None
    verbose: bool = False
    debug: bool = False
    json: bool = False
    quiet: bool = False

    def normalize(self) -> None:
        if self.debug:
            self.verbose = True
        if self.verbose:
            self.compact = False


@dataclass
class RuntimeContext:
    options: GlobalOptions
    config: Dict[str, Any]
    isatty: bool
    version: str

    @property
    def ns(self) -> Any:  # pragma: no cover - thin proxy
        return ns


def build_context(options: GlobalOptions) -> RuntimeContext:
    config = _cfg.get()
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    version = getattr(ns, "__version__", "unknown")
    return RuntimeContext(
        options=options,
        config=config,
        isatty=is_tty,
        version=version,
    )
