"""
Noēsis — intuition-guided agentic reasoning.

Stable public API (v0.3.0):
    run(task, *, seed=0, intuition=True, tags=None) -> str
    solve(task, *, using, seed=0, intuition=True, tags=None) -> str
    summary(episode_id) -> dict
    events(episode_id, *, stream=False) -> list[dict] | Iterator[dict]
    list_runs(limit=50, since=None) -> list[dict]
    set(**overrides) -> None
    Intuition, DirectedIntuition, NoesisVeto
"""

from __future__ import annotations

# Package metadata
__version__ = "0.3.1"
__schema_version__ = "1.0.0"

# Core execution API
from .core import solve, run, set

# Read/inspect API 
from .io import summary, events, list_runs
# Ergonomic intuition surface 
from .intuition import Intuition
from .direction import DirectedIntuition
from .exceptions import NoesisVeto

__all__ = (
    # core
    "solve",
    "run",
    "set",
    "summary",
    "events",
    "list_runs",
    # intuition
    "Intuition",
    "DirectedIntuition",
    "NoesisVeto",
)
