from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode

CONFIG_FILE_CANDIDATES: tuple[str, ...] = ("noesis.toml", ".noesis.toml")

ALLOWED_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "runs_dir",
        "agents",
        "tasks",
        "timeout_sec",
        "intuition_mode",
        "direction_min_confidence",
        "policy_aliases",
        "learn_mode",
        "learn_home",
        "learn_auto_apply_min_successes",
        "learn_auto_apply_min_confidence",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Pure runtime configuration value object."""

    runs_dir: Path
    agents: str
    tasks: str
    timeout_sec: int
    intuition_mode: IntuitionMode
    direction_min_confidence: float
    policy_aliases: dict[str, str]
    learn_mode: LearnMode
    learn_home: Path
    learn_auto_apply_min_successes: int
    learn_auto_apply_min_confidence: float


def default_runtime_config() -> RuntimeConfig:
    """Return the immutable default configuration."""
    return RuntimeConfig(
        runs_dir=Path("runs"),
        agents="agents.yaml",
        tasks="tasks.yaml",
        timeout_sec=60,
        intuition_mode=IntuitionMode.ADVISORY,
        direction_min_confidence=0.5,
        policy_aliases={},
        learn_mode=LearnMode.RECORD,
        learn_home=Path.home() / ".noesis" / "state",
        learn_auto_apply_min_successes=3,
        learn_auto_apply_min_confidence=0.75,
    )


def apply_runtime_overrides(
    config: RuntimeConfig,
    overrides: Mapping[str, object],
) -> RuntimeConfig:
    """Return a new config with validated overrides applied."""
    if not overrides:
        return config

    unknown = set(overrides) - ALLOWED_CONFIG_KEYS
    if unknown:
        allowed = ", ".join(sorted(ALLOWED_CONFIG_KEYS))
        bad = ", ".join(sorted(unknown))
        raise ValueError(f"unknown config keys: {bad} (allowed: {allowed})")

    updated = config

    for key, value in overrides.items():
        if key == "runs_dir":
            path = Path(value).expanduser()
            updated = replace(updated, runs_dir=path)
        elif key == "agents":
            updated = replace(updated, agents=str(value))
        elif key == "tasks":
            updated = replace(updated, tasks=str(value))
        elif key == "timeout_sec":
            timeout = int(value)
            if timeout <= 0:
                raise ValueError("timeout_sec must be > 0")
            updated = replace(updated, timeout_sec=timeout)
        elif key == "intuition_mode":
            updated = replace(updated, intuition_mode=_parse_intuition_mode(value))
        elif key == "direction_min_confidence":
            updated = replace(
                updated,
                direction_min_confidence=_bounded_float(value, "direction_min_confidence"),
            )
        elif key == "policy_aliases":
            if not isinstance(value, Mapping):
                raise ValueError("policy_aliases must be a mapping of alias -> spec")
            normalized = {str(k): str(v) for k, v in value.items()}
            updated = replace(updated, policy_aliases=normalized)
        elif key == "learn_mode":
            updated = replace(updated, learn_mode=_parse_learn_mode(value))
        elif key == "learn_home":
            updated = replace(updated, learn_home=Path(value).expanduser())
        elif key == "learn_auto_apply_min_successes":
            successes = int(value)
            if successes < 1:
                raise ValueError("learn_auto_apply_min_successes must be >= 1")
            updated = replace(updated, learn_auto_apply_min_successes=successes)
        elif key == "learn_auto_apply_min_confidence":
            updated = replace(
                updated,
                learn_auto_apply_min_confidence=_bounded_float(
                    value,
                    "learn_auto_apply_min_confidence",
                ),
            )
    return updated


def _parse_intuition_mode(value: object) -> IntuitionMode:
    if isinstance(value, IntuitionMode):
        return value
    if isinstance(value, str):
        return IntuitionMode(value.lower().strip())
    raise TypeError(f"unsupported intuition_mode value: {value!r}")


def _parse_learn_mode(value: object) -> LearnMode:
    if isinstance(value, LearnMode):
        return value
    if isinstance(value, str):
        return LearnMode(value.lower().strip())
    raise TypeError(f"unsupported learn_mode value: {value!r}")


def _bounded_float(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a float-compatible value") from exc
    if not (0.0 <= number <= 1.0):
        raise ValueError(f"{label} must be within [0.0, 1.0]")
    return number
