from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence
import sys

import noesis as ns
from noesis.interfaces.config import ConfigSnapshot
from noesis.runtime.config_provider import RuntimeContext
from noesis.runtime.session import NoesisSession
from noesis.runtime.session.models import SessionConfig
from .runtime_context import load_runtime_context


@dataclass
class GlobalOptions:
    compact: bool | None = None
    verbose: bool = False
    debug: bool = False
    json: bool = False
    quiet: bool = False
    force_rich: bool = False

    def normalize(self) -> None:
        if self.debug:
            self.verbose = True
        if self.verbose:
            self.compact = False


@dataclass
class CLIContext:
    options: GlobalOptions
    config: Dict[str, Any]
    isatty: bool
    version: str
    runtime_context: RuntimeContext
    config_snapshot: ConfigSnapshot
    session: NoesisSession

    @property
    def ns(self) -> Any:  # pragma: no cover - thin proxy
        return ns


def build_context(options: GlobalOptions, port_specs: Sequence[str]) -> CLIContext:
    if port_specs:
        runtime_ctx = load_runtime_context(port_specs)
        config_port = runtime_ctx.require("config", getattr(runtime_ctx.config_port, "__api_version__", "config/1.0-rc1"))
        snapshot = config_port.get()
        session = NoesisSession(config=SessionConfig(snapshot=snapshot, default_tags={}), context=runtime_ctx)
    else:
        session = ns.session_provider().current()
        runtime_ctx = session.context
        snapshot = session.config_snapshot

    config = snapshot.to_mapping()
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    version = getattr(ns, "__version__", "unknown")
    return CLIContext(
        options=options,
        config=config,
        isatty=is_tty,
        version=version,
        runtime_context=runtime_ctx,
        config_snapshot=snapshot,
        session=session,
    )
