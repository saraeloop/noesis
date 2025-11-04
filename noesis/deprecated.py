from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

try:  # pragma: no cover - availability is tested via CLI flow
    from rich.console import Console
    from rich.panel import Panel
    _HAS_RICH = True
except Exception:  # noqa: BLE001
    Console = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    _HAS_RICH = False

LEGACY_ENV_VAR = "NOESIS_LEGACY_SHIMS"
UPGRADE_DOC_ANCHOR = "docs/app/guides/upgrading-to-v0.9"


@dataclass(frozen=True)
class RemovedSymbol:
    fq_name: str
    replacement: str
    removed_in: str
    deprecated_since: str
    module_removed: bool = False

    @property
    def module(self) -> str:
        if self.module_removed:
            return self.fq_name
        module, _, _ = self.fq_name.rpartition(".")
        return module

    @property
    def symbol(self) -> str:
        if self.module_removed:
            return ""
        _, _, symbol = self.fq_name.rpartition(".")
        return symbol


REMOVED_SYMBOLS: Tuple[RemovedSymbol, ...] = (
    RemovedSymbol(
        fq_name="noesis.summary.load",
        replacement="noesis.summary.read",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.summary.finalize_summary",
        replacement="noesis.summary.finalize",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.start_event",
        replacement="noesis.events.start",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.observe_event",
        replacement="noesis.events.observe",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.interpret_event",
        replacement="noesis.events.interpret",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.plan_event",
        replacement="noesis.events.plan",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.act_event",
        replacement="noesis.events.act",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.reflect_event",
        replacement="noesis.events.reflect",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.direction_event",
        replacement="noesis.events.direction",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.ensure_act_event",
        replacement="noesis.events.ensure",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.events.terminate_event",
        replacement="noesis.events.terminate",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
    ),
    RemovedSymbol(
        fq_name="noesis.state.store",
        replacement="noesis.episode.EpisodeIndex",
        removed_in="v0.9.0",
        deprecated_since="v0.8.x",
        module_removed=True,
    ),
)

REMOVED_SYMBOL_MAP: Dict[str, RemovedSymbol] = {sym.fq_name: sym for sym in REMOVED_SYMBOLS}

_LEGACY_ENABLED = None
_WARNED: Dict[str, bool] = {}


def legacy_shims_enabled() -> bool:
    global _LEGACY_ENABLED
    if _LEGACY_ENABLED is None:
        value = os.environ.get(LEGACY_ENV_VAR, "")
        _LEGACY_ENABLED = value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_LEGACY_ENABLED)


def _format_warning_message(symbol: RemovedSymbol) -> str:
    return (
        f"Legacy shim active for {symbol.fq_name} — removed in {symbol.removed_in} "
        f"(deprecated since {symbol.deprecated_since}). "
        f"Use {symbol.replacement}. See {UPGRADE_DOC_ANCHOR} for migration details."
    )


def emit_legacy_warning(symbol_name: str) -> None:
    symbol = REMOVED_SYMBOL_MAP.get(symbol_name)
    if not symbol:
        return
    if _WARNED.get(symbol_name):
        return
    message = _format_warning_message(symbol)
    if _HAS_RICH and Console is not None and Panel is not None:
        console = Console(stderr=True)
        console.print(
            Panel.fit(
                message,
                title="⚠️  Legacy shim enabled",
                border_style="yellow",
            )
        )
    else:
        sys.stderr.write(f"[NOESIS] {message}\n")
    warnings.warn(message, DeprecationWarning, stacklevel=3)
    _WARNED[symbol_name] = True


def iter_removed_symbols() -> Iterable[RemovedSymbol]:
    return REMOVED_SYMBOLS
