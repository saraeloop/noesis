"""Ports and data contracts for configuration access within Noēsis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Protocol

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode

__all__ = ["ConfigSnapshot", "ConfigPort"]


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Immutable view of runtime configuration values."""

    runs_dir: Path
    agents: str
    tasks: str
    timeout_sec: int
    intuition_mode: IntuitionMode
    direction_min_confidence: float
    policy_aliases: Dict[str, str]
    learn_mode: LearnMode
    learn_home: Path
    learn_auto_apply_min_successes: int
    learn_auto_apply_min_confidence: float

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ConfigSnapshot":
        """Build a snapshot from a loose mapping of config values."""
        def _intuition_mode(raw: Any) -> IntuitionMode:
            if isinstance(raw, IntuitionMode):
                return raw
            if isinstance(raw, str):
                return IntuitionMode(raw.lower().strip())
            raise TypeError(f"Unsupported intuition_mode value: {raw!r}")

        def _learn_mode(raw: Any) -> LearnMode:
            if isinstance(raw, LearnMode):
                return raw
            if isinstance(raw, str):
                return LearnMode(raw.lower().strip())
            raise TypeError(f"Unsupported learn_mode value: {raw!r}")

        raw_aliases = data.get("policy_aliases", {})
        if raw_aliases is None:
            raw_aliases = {}
        if not isinstance(raw_aliases, Mapping):
            raise TypeError(f"policy_aliases must be a mapping, got: {raw_aliases!r}")

        return cls(
            runs_dir=Path(str(data["runs_dir"])),
            agents=str(data["agents"]),
            tasks=str(data["tasks"]),
            timeout_sec=int(data["timeout_sec"]),
            intuition_mode=_intuition_mode(data["intuition_mode"]),
            direction_min_confidence=float(data["direction_min_confidence"]),
            policy_aliases={str(key): str(value) for key, value in raw_aliases.items()},
            learn_mode=_learn_mode(data["learn_mode"]),
            learn_home=Path(str(data["learn_home"])),
            learn_auto_apply_min_successes=int(
                data["learn_auto_apply_min_successes"]
            ),
            learn_auto_apply_min_confidence=float(
                data["learn_auto_apply_min_confidence"]
            ),
        )

    def to_mapping(self) -> Dict[str, object]:
        """Represent the snapshot as a plain dictionary."""
        return {
            "runs_dir": str(self.runs_dir),
            "agents": self.agents,
            "tasks": self.tasks,
            "timeout_sec": int(self.timeout_sec),
            "intuition_mode": self.intuition_mode.value,
            "direction_min_confidence": float(self.direction_min_confidence),
            "policy_aliases": dict(self.policy_aliases),
            "learn_mode": self.learn_mode.value,
            "learn_home": str(self.learn_home),
            "learn_auto_apply_min_successes": int(
                self.learn_auto_apply_min_successes
            ),
            "learn_auto_apply_min_confidence": float(
                self.learn_auto_apply_min_confidence
            ),
        }


class ConfigPort(Protocol):
    """Boundary for retrieving and updating runtime configuration."""

    def get(self) -> ConfigSnapshot:
        """Return the current configuration snapshot."""

    def set(self, **overrides: object) -> ConfigSnapshot:
        """Apply overrides and return the updated snapshot."""

    def reload(self) -> ConfigSnapshot:
        """Reload configuration from persistence layers."""
