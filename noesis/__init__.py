"""
Noēsis — intuition-guided agentic reasoning.

Stable public API:
    solve(task, *, using, seed=0, intuition=True, tags=None) -> str
    run(task, *, seed=0, intuition=True, tags=None) -> str
    run_using(*, using, task, seed=0, intuition=True, tags=None) -> str
    run_graph(kind, *, task, seed=0, intuition=True, tags=None) -> str  # compat alias
    summary(episode_id) -> dict
    events(episode_id, *, stream=False) -> list[dict] | Iterator[dict]
    metrics(episode_id) -> dict
    list_runs(limit=50, since=None) -> list[dict]
    last() -> str | None
    set(**overrides) -> None
    paths(episode_id) -> dict
"""

from __future__ import annotations

# Package metadata
__version__ = "0.2.0"
__schema_version__ = "1.0.0"

# Core execution API
from .core import solve, run, run_using, run_graph, set

# Read/inspect API 
from .io import summary, events, metrics, paths, last, list_runs
# Ergonomic intuition surface 
from .intuition import Intuition, IntuitionEvent, NullIntuition, IntuitionMode
from .direction import DirectedIntuition, DirectiveKind
from .exceptions import NoesisError, NoesisVeto

__all__ = (
    # core
    "solve",
    "run",
    "run_using",
    "run_graph",
    "set",
    "summary",
    "events",
    "metrics",
    "paths",
    "last",
    "list_runs",
    # intuition
    "Intuition",
    "IntuitionEvent",
    "NullIntuition",
    "DirectedIntuition",
    "DirectiveKind",
    "IntuitionMode",
    "NoesisError",
    "NoesisVeto",
)
