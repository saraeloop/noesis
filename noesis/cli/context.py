from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence
import sys

import noesis as ns
from noesis.interfaces.config import ConfigSnapshot
from noesis.runtime.config_provider import RuntimeContainer
from .container import build_cli_container


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
    container: RuntimeContainer
    config_snapshot: ConfigSnapshot

    @property
    def ns(self) -> Any:  # pragma: no cover - thin proxy
        return ns


def build_context(options: GlobalOptions, port_specs: Sequence[str]) -> RuntimeContext:
    container = build_cli_container(port_specs)
    config_port = container.require("config", getattr(container.config_port, "__api_version__", "config/1.0-rc1"))
    snapshot = config_port.get()
    config = snapshot.to_mapping()
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    version = getattr(ns, "__version__", "unknown")
    return RuntimeContext(
        options=options,
        config=config,
        isatty=is_tty,
        version=version,
        container=container,
        config_snapshot=snapshot,
    )
