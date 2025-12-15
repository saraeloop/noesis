from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Literal, Optional

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.interfaces.config import PlannerMode

CONFIG_FILE_CANDIDATES: tuple[str, ...] = ("noesis.toml", ".noesis.toml")

ALLOWED_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "runs_dir",
        "agents",
        "tasks",
        "timeout_sec",
        "intuition_mode",
        "direction_min_confidence",
        "planner_mode",
        "policy_aliases",
        "learn_mode",
        "learn_home",
        "learn_auto_apply_min_successes",
        "learn_auto_apply_min_confidence",
        "prompt_provenance_enabled",
        "prompt_provenance_mode",
        "governance_mode",
        "governance_failure_policy",
        "governance_timeout_ms",
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
    planner_mode: PlannerMode
    policy_aliases: dict[str, str]
    learn_mode: LearnMode
    learn_home: Path
    learn_auto_apply_min_successes: int
    learn_auto_apply_min_confidence: float
    prompt_provenance_enabled: bool
    prompt_provenance_mode: Literal["full", "hash_only", "redacted"]
    governance_mode: str
    governance_failure_policy: Optional[str]
    governance_timeout_ms: Optional[int]


def default_runtime_config() -> RuntimeConfig:
    """Return the immutable default configuration."""
    return RuntimeConfig(
        runs_dir=Path("runs"),
        agents="agents.yaml",
        tasks="tasks.yaml",
        timeout_sec=60,
        intuition_mode=IntuitionMode.ADVISORY,
        direction_min_confidence=0.5,
        planner_mode=PlannerMode.META,
        policy_aliases={},
        learn_mode=LearnMode.RECORD,
        learn_home=Path.home() / ".noesis" / "state",
        learn_auto_apply_min_successes=3,
        learn_auto_apply_min_confidence=0.75,
        prompt_provenance_enabled=False,
        prompt_provenance_mode="hash_only",
        governance_mode="off",
        governance_failure_policy=None,
        governance_timeout_ms=None,
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
        elif key == "planner_mode":
            updated = replace(updated, planner_mode=_parse_planner_mode(value))
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
        elif key == "prompt_provenance_enabled":
            updated = replace(updated, prompt_provenance_enabled=_parse_bool(value, "prompt_provenance_enabled"))
        elif key == "prompt_provenance_mode":
            updated = replace(updated, prompt_provenance_mode=_parse_provenance_mode(value))
        elif key == "governance_mode":
            updated = replace(updated, governance_mode=_parse_governance_mode(value))
        elif key == "governance_failure_policy":
            updated = replace(
                updated,
                governance_failure_policy=_parse_governance_failure_policy(value),
            )
        elif key == "governance_timeout_ms":
            updated = replace(updated, governance_timeout_ms=_parse_timeout_ms(value))
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


def _parse_planner_mode(value: object) -> PlannerMode:
    if isinstance(value, PlannerMode):
        return value
    if isinstance(value, str):
        return PlannerMode(value.lower().strip())
    raise TypeError(f"unsupported planner_mode value: {value!r}")


def _bounded_float(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a float-compatible value") from exc
    if not (0.0 <= number <= 1.0):
        raise ValueError(f"{label} must be within [0.0, 1.0]")
    return number


def _parse_bool(value: object, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise TypeError(f"{label} must be a bool-compatible value, got {value!r}")


def _parse_provenance_mode(value: object) -> Literal["full", "hash_only", "redacted"]:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("full", "hash_only", "redacted"):
            if normalized == "full":
                return "full"
            if normalized == "redacted":
                return "redacted"
            return "hash_only"
    raise ValueError("prompt_provenance_mode must be 'full', 'hash_only', or 'redacted'")


def _parse_governance_mode(value: object) -> str:
    try:
        from noesis.domain.faculties.governance import GovernanceMode  # local import to avoid cycle
    except Exception:  # pragma: no cover - fallback
        GovernanceMode = None  # type: ignore

    if GovernanceMode is not None and isinstance(value, GovernanceMode):
        return value.value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        if normalized in {"off", "audit", "enforce"}:
            return normalized
    raise ValueError("governance_mode must be 'off', 'audit', or 'enforce'")


def _parse_governance_failure_policy(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        if normalized in {"fail_open", "fail_closed"}:
            return normalized
    # Allow enum instances passed through ns.set
    try:
        from noesis.domain.faculties.governance import GovernanceFailurePolicy  # local import to avoid cycle

        if isinstance(value, GovernanceFailurePolicy):
            return value.value
    except Exception:
        pass
    raise ValueError("governance_failure_policy must be 'fail_open' or 'fail_closed'")


def _parse_timeout_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("governance_timeout_ms must be an int") from exc
    if timeout <= 0:
        raise ValueError("governance_timeout_ms must be > 0")
    return timeout
