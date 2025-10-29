# noesis/config.py
"""
Global, minimally invasive configuration for Noēsis.

Design:
- Tiny set of knobs (paths, agents file, tasks file, timeouts, intuition mode).
- Stored in a module-level dataclass; only `set()` mutates.
- `get()` returns a plain, JSON-friendly dict (no Path/Enum leakage).
"""
# noesis/config.py
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Any, Dict, Optional
import builtins as _builtins
import tomllib

from .intuition.mode import IntuitionMode

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_AGENTS = "agents.yaml"
DEFAULT_TASKS = "tasks.yaml"
DEFAULT_DIRECTION_MIN_CONFIDENCE = 0.5
CONFIG_FILE_CANDIDATES = ("noesis.toml", ".noesis.toml")
ALLOWED_KEYS = {"runs_dir", "agents", "tasks", "timeout_sec", "intuition_mode", "direction_min_confidence"}

@dataclass(frozen=True)
class Config:
    runs_dir: Path = DEFAULT_RUNS_DIR
    agents: str = DEFAULT_AGENTS
    tasks: str = DEFAULT_TASKS
    timeout_sec: int = 60
    intuition_mode: IntuitionMode = IntuitionMode.ADVISORY
    direction_min_confidence: float = DEFAULT_DIRECTION_MIN_CONFIDENCE

_config: Config = Config()

def _normalize_intuition_mode(val: Any) -> IntuitionMode:
    if isinstance(val, IntuitionMode):
        return val
    if isinstance(val, str):
        return IntuitionMode(val.lower().strip())
    raise ValueError(f"invalid intuition_mode: {val!r}")

def get() -> Dict[str, Any]:
    c = asdict(_config)
    c["runs_dir"] = str(_config.runs_dir)
    c["intuition_mode"] = _config.intuition_mode.value
    c["direction_min_confidence"] = float(_config.direction_min_confidence)
    return c

def set(**overrides: Any) -> None:
    """
    Update global config. Supported keys:
        runs_dir: str | Path
        agents: str
        tasks: str
        timeout_sec: int
        intuition_mode: str | IntuitionMode
        direction_min_confidence: float
    """
    global _config

    unknown = _builtins.set(overrides) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")

    new = _config
    if "runs_dir" in overrides:
        new = replace(new, runs_dir=Path(overrides["runs_dir"]))
    if "agents" in overrides:
        new = replace(new, agents=str(overrides["agents"]))
    if "tasks" in overrides:
        new = replace(new, tasks=str(overrides["tasks"]))
    if "timeout_sec" in overrides:
        new = replace(new, timeout_sec=int(overrides["timeout_sec"]))
    if "intuition_mode" in overrides:
        mode = _normalize_intuition_mode(overrides["intuition_mode"])
        new = replace(new, intuition_mode=mode)
    if "direction_min_confidence" in overrides:
        new = replace(new, direction_min_confidence=float(overrides["direction_min_confidence"]))

    _config = new


def _load_config_file() -> None:
    for name in CONFIG_FILE_CANDIDATES:
        path = Path.cwd() / name
        if not path.is_file():
            continue
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        table = data.get("noesis", data)
        overrides: Dict[str, Any] = {}
        for key in ALLOWED_KEYS:
            if key in table:
                overrides[key] = table[key]
        if overrides:
            set(**overrides)
        break


_load_config_file()
