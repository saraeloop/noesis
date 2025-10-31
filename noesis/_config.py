"""
Internal configuration plumbing for Noēsis.

External callers should prefer the high-level `noesis.set(...)` API.
The functions defined here are imported by other modules within the
package; they are not part of the public surface.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, replace, field
from pathlib import Path
from typing import Any, Dict, Optional
import builtins as _builtins
import os
import tomllib
import warnings

from .intuition import IntuitionMode
from .learn import LearnMode

__all__ = [
    "Config",
    "DEFAULT_RUNS_DIR",
    "DEFAULT_AGENTS",
    "DEFAULT_TASKS",
    "DEFAULT_DIRECTION_MIN_CONFIDENCE",
    "DEFAULT_TIMEOUT_SEC",
    "DEFAULT_POLICY_ALIASES",
    "DEFAULT_LEARN_MODE",
    "DEFAULT_LEARN_HOME",
    "get",
    "set",
    "reset",
    "reload_from_disk_and_env",
]

# Defaults & allowed keys

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_AGENTS = "agents.yaml"
DEFAULT_TASKS = "tasks.yaml"
DEFAULT_DIRECTION_MIN_CONFIDENCE = 0.5
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_POLICY_ALIASES: Dict[str, str] = {}
DEFAULT_LEARN_MODE = LearnMode.RECORD
DEFAULT_LEARN_HOME = Path.home() / ".noesis" / "state"

CONFIG_FILE_CANDIDATES = ("noesis.toml", ".noesis.toml")

ALLOWED_KEYS = {
    "runs_dir",
    "agents",
    "tasks",
    "timeout_sec",
    "intuition_mode",
    "direction_min_confidence",
    "policy_aliases",
    "learn_mode",
    "learn_home",
}


@dataclass(frozen=True)
class Config:
    runs_dir: Path = DEFAULT_RUNS_DIR
    agents: str = DEFAULT_AGENTS
    tasks: str = DEFAULT_TASKS
    timeout_sec: int = DEFAULT_TIMEOUT_SEC
    intuition_mode: IntuitionMode = IntuitionMode.ADVISORY
    direction_min_confidence: float = DEFAULT_DIRECTION_MIN_CONFIDENCE
    policy_aliases: Dict[str, str] = field(default_factory=dict)
    learn_mode: LearnMode = DEFAULT_LEARN_MODE
    learn_home: Path = DEFAULT_LEARN_HOME


_config: Config = Config()


def _normalize_intuition_mode(val: Any) -> IntuitionMode:
    if isinstance(val, IntuitionMode):
        return val
    if isinstance(val, str):
        return IntuitionMode(val.lower().strip())
    raise ValueError(f"invalid intuition_mode: {val!r}")


def _normalize_learn_mode(val: Any) -> LearnMode:
    if isinstance(val, LearnMode):
        return val
    if isinstance(val, str):
        return LearnMode(val.lower().strip())
    raise ValueError(f"invalid learn_mode: {val!r}")


def _find_config_path() -> Optional[Path]:
    cur = Path.cwd()
    for parent in (cur, *cur.parents):
        for name in CONFIG_FILE_CANDIDATES:
            p = parent / name
            if p.is_file():
                return p
    return None


def _load_config_file() -> None:
    path = _find_config_path()
    if not path:
        return
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    table = data.get("noesis", data)
    overrides: Dict[str, Any] = {k: table[k] for k in ALLOWED_KEYS if k in table}
    if overrides:
        set(**overrides)


def _load_env_overrides() -> None:
    env: Dict[str, Any] = {}
    if "NOESIS_RUNS_DIR" in os.environ:
        env["runs_dir"] = os.environ["NOESIS_RUNS_DIR"]
    if "NOESIS_AGENTS" in os.environ:
        env["agents"] = os.environ["NOESIS_AGENTS"]
    if "NOESIS_TASKS" in os.environ:
        env["tasks"] = os.environ["NOESIS_TASKS"]
    if "NOESIS_TIMEOUT_SEC" in os.environ:
        env["timeout_sec"] = os.environ["NOESIS_TIMEOUT_SEC"]
    if "NOESIS_INTUITION_MODE" in os.environ:
        env["intuition_mode"] = os.environ["NOESIS_INTUITION_MODE"]
    if "NOESIS_DIRECTION_MIN_CONFIDENCE" in os.environ:
        env["direction_min_confidence"] = os.environ["NOESIS_DIRECTION_MIN_CONFIDENCE"]
    elif "NOESIS_DIR_MIN_CONFIDENCE" in os.environ:
        warnings.warn(
            "NOESIS_DIR_MIN_CONFIDENCE is deprecated; use NOESIS_DIRECTION_MIN_CONFIDENCE",
            FutureWarning,
            stacklevel=2,
        )
        env["direction_min_confidence"] = os.environ["NOESIS_DIR_MIN_CONFIDENCE"]
    if "NOESIS_LEARN_MODE" in os.environ:
        env["learn_mode"] = os.environ["NOESIS_LEARN_MODE"]
    if "NOESIS_LEARN_HOME" in os.environ:
        env["learn_home"] = os.environ["NOESIS_LEARN_HOME"]
    if env:
        set(**env)


def get() -> Dict[str, Any]:
    c = asdict(_config)
    c["runs_dir"] = str(_config.runs_dir)
    c["intuition_mode"] = _config.intuition_mode.value
    c["direction_min_confidence"] = float(_config.direction_min_confidence)
    c["policy_aliases"] = dict(_config.policy_aliases)
    c["learn_mode"] = _config.learn_mode.value
    c["learn_home"] = str(_config.learn_home)
    return c


def set(**overrides: Any) -> None:
    global _config

    unknown = _builtins.set(overrides) - ALLOWED_KEYS
    if unknown:
        allowed = ", ".join(sorted(ALLOWED_KEYS))
        bad = ", ".join(sorted(unknown))
        raise ValueError(f"unknown config keys: {bad} (allowed: {allowed})")

    new = _config

    if "runs_dir" in overrides:
        rd = Path(overrides["runs_dir"])
        rd.mkdir(parents=True, exist_ok=True)
        new = replace(new, runs_dir=rd)

    if "agents" in overrides:
        new = replace(new, agents=str(overrides["agents"]))

    if "tasks" in overrides:
        new = replace(new, tasks=str(overrides["tasks"]))

    if "timeout_sec" in overrides:
        ts = int(overrides["timeout_sec"])
        if ts <= 0:
            raise ValueError("timeout_sec must be > 0")
        new = replace(new, timeout_sec=ts)

    if "intuition_mode" in overrides:
        mode = _normalize_intuition_mode(overrides["intuition_mode"])
        new = replace(new, intuition_mode=mode)

    if "direction_min_confidence" in overrides:
        val = float(overrides["direction_min_confidence"])
        if not (0.0 <= val <= 1.0):
            raise ValueError("direction_min_confidence must be within [0.0, 1.0]")
        new = replace(new, direction_min_confidence=val)

    if "policy_aliases" in overrides:
        aliases = overrides["policy_aliases"]
        if not isinstance(aliases, dict):
            raise ValueError("policy_aliases must be a mapping of alias -> spec")
        normalized = {str(k): str(v) for k, v in aliases.items()}
        new = replace(new, policy_aliases=normalized)

    if "learn_mode" in overrides:
        mode = _normalize_learn_mode(overrides["learn_mode"])
        new = replace(new, learn_mode=mode)

    if "learn_home" in overrides:
        home = Path(overrides["learn_home"]).expanduser()
        home.mkdir(parents=True, exist_ok=True)
        new = replace(new, learn_home=home)

    _config = new


def reset() -> None:
    global _config
    _config = Config()


def reload_from_disk_and_env() -> None:
    _load_env_overrides()
    _load_config_file()


_load_env_overrides()
_load_config_file()
