"""
Noēsis — a cognitive framework for observable, adaptive reasoning.

Stable public API (v0.5.0):
    run(task, *, seed=0, intuition=True, tags=None) -> str
    solve(task, *, using, seed=0, intuition=True, tags=None) -> str
    summary(episode_id) -> dict
    events(episode_id, *, stream=False) -> list[dict] | Iterator[dict]
    list_runs(limit=50, since=None) -> list[dict]
    set(**overrides) -> None
    Intuition, DirectedIntuition, NoesisVeto, MinimalPlanner
"""


from __future__ import annotations

from .trace.schema import SUMMARY_SCHEMA_VERSION

# Package metadata
__version__ = "0.5.1"
__schema_version__ = SUMMARY_SCHEMA_VERSION

# Core execution API
from .core import solve, run, run_using, set

try:  # v0.5+ forward-compatibility
    from .runtime.config_provider import get_config_port

    def get() -> dict[str, object]:
        """Public accessor returning legacy dict-based payloads."""
        return get_config_port().get().to_mapping()
except Exception:  # pragma: no cover - fallback until new config lands
    from ._config import get  # type: ignore
from .domain.planner.minimal import MinimalPlanner

# Read/inspect API 
from .io import summary, events, list_runs, paths
# Ergonomic intuition surface 
from .intuition import Intuition
from .direction import DirectedIntuition
from .exceptions import NoesisVeto

__all__ = (
    # core
    "solve",
    "run",
    "run_using",
    "set",
    "get",
    "summary",
    "events",
    "list_runs",
    "paths",
    "MinimalPlanner",
    # intuition
    "Intuition",
    "DirectedIntuition",
    "NoesisVeto",
)
