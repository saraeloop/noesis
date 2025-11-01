"""
Episodes: canonical run identity and summary lifecycle for Noēsis.

Purpose
-------
- Generate collision-resistant, human-readable episode IDs.
- Create a per-episode run directory atomically (`begin_episode`).
- Provide a typed container (`EpisodeSummary`) for final summaries
  that serialize cleanly to JSON and remain schema-friendly.

ID Format
---------
    ep_YYYYMMDD_HHMMSS_microseconds_<4hex>_s{seed}

Guarantees
----------
- IDs include UTC wall-clock time plus random nonce for uniqueness.
- `begin_episode()` creates the run directory with retry-on-collision.
- `EpisodeSummary` is a plain dataclass designed for stable JSON output.

Usage
-----
    episode_id = new_episode_id(seed)
    run_dir = begin_episode("./runs", episode_id)
    summary = EpisodeSummary(...);  # later persisted by trace helpers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import time
from os import urandom

__all__ = ["new_episode_id", "EpisodeSummary", "hash_config", "begin_episode"]


# Identity

def new_episode_id(seed: int) -> str:
    """
    Return a collision-resistant episode ID.

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
    ports: Dict[str, str] = field(default_factory=dict)


def hash_config(blob: bytes) -> str:
    """Return a stable content hash label for agent/config blobs."""
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"


# Lifecycle

def begin_episode(base: str, episode_id: str, *, retries: int = 3) -> Path:
    """
    Create a unique run directory for an episode under `base`.

    Retries on rare ID collisions by regenerating a new ID.
    Returns the path to the newly created directory.
    """
    base_p = Path(base)
    base_p.mkdir(parents=True, exist_ok=True)

    eid = episode_id
    for i in range(retries + 1):
        d = base_p / eid
        try:
            d.mkdir(mode=0o755, exist_ok=False)
            return d
        except FileExistsError:
            # regenerate only on collision (extremely rare)
            eid = new_episode_id(seed=0)
            # tiny backoff except on final attempt
            if i < retries:
                time.sleep(0.001)

    raise RuntimeError("Failed to create unique run directory after retries")
