"""
Canonical episode state & identifiers.

Notes:
- Episode IDs are deterministic and human-readable.
- State is a plain dict for LangGraph compatibility, but we offer helpers.
- begin_episode() creates a unique directory for each run.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
import hashlib, time, os
from os import urandom

# Identity 

def new_episode_id(seed: int) -> str:
    """
    Collision-resistant episode id.

    Format:
      ep_YYYYMMDD_HHMMSS_microseconds_<4hex>_s{seed}
    """
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    nonce = urandom(2).hex()  # 4 hex chars
    return f"ep_{now}_{nonce}_s{seed}"

# State 

@dataclass
class EpisodeSummary:
    schema_version: str
    episode_id: str
    task: str
    seed: int
    started_at: str
    duration_sec: float | None = None
    flags: Dict[str, Any] = field(default_factory=dict)
    agents_config_hash: str = ""
    hints: List[Dict[str, Any]] = field(default_factory=list)
    risk_forecast: List[Dict[str, Any]] = field(default_factory=list)
    answer: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, Any] = field(default_factory=dict)

# Integrity 

def hash_config(blob: bytes) -> str:
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"

# Lifecycle 

def begin_episode(base: str, episode_id: str, *, retries: int = 3) -> Path:
    """
    Begin a new Noēsis episode.

    Creates a unique directory for this episode under `base`.
    Ensures atomic creation and retries in the rare case of collision.
    Returns the Path to the newly created run directory.
    """
    base_p = Path(base)
    base_p.mkdir(parents=True, exist_ok=True)

    for i in range(retries + 1):
        d = base_p / episode_id
        try:
            d.mkdir(mode=0o755, exist_ok=False)
            return d
        except FileExistsError:
            # regenerate only if collision (extremely rare)
            episode_id = new_episode_id(seed=0)
            time.sleep(0 if i == retries else 0.001)

    raise RuntimeError("Failed to create unique run directory after retries")