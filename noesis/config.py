"""
Global, minimally invasive configuration for Noēsis.

Design:
- Keep a tiny set of knobs (paths, agents file, tasks file, timeouts).
- Store in a module-level dict; avoid hidden state elsewhere.
- Only `set()` mutates config; reads are pure.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_AGENTS = "agents.yaml"
DEFAULT_TASKS = "tasks.yaml"

@dataclass
class Config:
    runs_dir: Path = DEFAULT_RUNS_DIR
    agents: str = DEFAULT_AGENTS
    tasks: str = DEFAULT_TASKS
    timeout_sec: int = 60

_config = Config()

def get() -> Dict[str, Any]:
    """Return a copy of the current config as plain dict (read-only to callers)."""
    c = asdict(_config)
    c["runs_dir"] = str(_config.runs_dir)
    return c

def set(**overrides: Any) -> None:
    """
    Update global config. Supported keys:
        runs_dir: str | Path
        agents: str
        tasks: str
        timeout_sec: int
    """
    global _config
    if "runs_dir" in overrides:
        _config.runs_dir = Path(overrides["runs_dir"])
    if "agents" in overrides:
        _config.agents = str(overrides["agents"])
    if "tasks" in overrides:
        _config.tasks = str(overrides["tasks"])
    if "timeout_sec" in overrides:
        _config.timeout_sec = int(overrides["timeout_sec"])