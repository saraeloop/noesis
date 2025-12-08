"""Ports and data contracts for configuration access within Noēsis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Protocol

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode

__all__ = ["ConfigSnapshot", "ConfigPort", "PlannerMode"]


class PlannerMode(str, Enum):
    MINIMAL = "minimal"
    META = "meta"


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Immutable view of runtime configuration values."""

    runs_dir: Path
    agents: str
    tasks: str
    timeout_sec: int
    intuition_mode: IntuitionMode
    direction_min_confidence: float
    planner_mode: PlannerMode
    policy_aliases: Dict[str, str]
    learn_mode: LearnMode
    learn_home: Path
    learn_auto_apply_min_successes: int
    learn_auto_apply_min_confidence: float
    prompt_provenance_enabled: bool
    prompt_provenance_mode: Literal["full", "hash_only", "redacted"]

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

        def _planner_mode(raw: Any) -> PlannerMode:
            if isinstance(raw, PlannerMode):
                return raw
            if isinstance(raw, str):
                return PlannerMode(raw.lower().strip())
            raise TypeError(f"Unsupported planner_mode value: {raw!r}")

        def _bool_value(raw: Any, label: str) -> bool:
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                normalized = raw.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
            raise TypeError(f"Unsupported {label} value: {raw!r}")

        def _prompt_mode(raw: Any) -> Literal["full", "hash_only", "redacted"]:
            if isinstance(raw, str):
                normalized = raw.strip().lower()
                if normalized in {"full", "hash_only", "redacted"}:
                    if normalized == "full":
                        return "full"
                    if normalized == "redacted":
                        return "redacted"
                    return "hash_only"
            raise TypeError(
                f"prompt_provenance_mode must be 'full', 'hash_only', or 'redacted', got: {raw!r}"
            )

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
            planner_mode=_planner_mode(data.get("planner_mode", PlannerMode.META.value)),
            policy_aliases={str(key): str(value) for key, value in raw_aliases.items()},
            learn_mode=_learn_mode(data["learn_mode"]),
            learn_home=Path(str(data["learn_home"])),
            learn_auto_apply_min_successes=int(
                data["learn_auto_apply_min_successes"]
            ),
            learn_auto_apply_min_confidence=float(
                data["learn_auto_apply_min_confidence"]
            ),
            prompt_provenance_enabled=_bool_value(
                data.get("prompt_provenance_enabled", False),
                "prompt_provenance_enabled",
            ),
            prompt_provenance_mode=_prompt_mode(
                data.get("prompt_provenance_mode", "hash_only")
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
            "planner_mode": self.planner_mode.value,
            "policy_aliases": dict(self.policy_aliases),
            "learn_mode": self.learn_mode.value,
            "learn_home": str(self.learn_home),
            "learn_auto_apply_min_successes": int(
                self.learn_auto_apply_min_successes
            ),
            "learn_auto_apply_min_confidence": float(
                self.learn_auto_apply_min_confidence
            ),
            "prompt_provenance_enabled": self.prompt_provenance_enabled,
            "prompt_provenance_mode": self.prompt_provenance_mode,
        }


class ConfigPort(Protocol):
    """Boundary for retrieving and updating runtime configuration."""

    __api_version__: str = "config/1.0-rc1"

    def get(self) -> ConfigSnapshot:
        """Return the current configuration snapshot."""

    def set(self, **overrides: object) -> ConfigSnapshot:
        """Apply overrides and return the updated snapshot."""

    def reload(self) -> ConfigSnapshot:
        """Reload configuration from persistence layers."""

    def supports(self, capability: str) -> bool:
        """Return True if the port exposes a named capability."""
