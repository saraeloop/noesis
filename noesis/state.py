"""
Canonical episode state & identifiers.

Notes:
- Episode IDs are deterministic and human-readable.
- State is a plain dict for LangGraph compatibility, but we offer helpers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib

def new_episode_id(seed: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ep_{now}_s{seed}"

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

def hash_config(blob: bytes) -> str:
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"