"""Infrastructure adapter that loads configuration from env variables and TOML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Sequence
import os
import tomllib
import warnings

from noesis.domain.config import (
    ALLOWED_CONFIG_KEYS,
    CONFIG_FILE_CANDIDATES,
    RuntimeConfig,
    apply_runtime_overrides,
    default_runtime_config,
)
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode

from .utils import find_config_path

__all__ = ["EnvTomlConfig"]

_EnvMap = Mapping[str, str]
_TomlLoader = Callable[[Path], Mapping[str, object]]

_ENV_KEY_MAP: dict[str, str] = {
    "NOESIS_RUNS_DIR": "runs_dir",
    "NOESIS_AGENTS": "agents",
    "NOESIS_TASKS": "tasks",
    "NOESIS_TIMEOUT_SEC": "timeout_sec",
    "NOESIS_INTUITION_MODE": "intuition_mode",
    "NOESIS_DIRECTION_MIN_CONFIDENCE": "direction_min_confidence",
    "NOESIS_PLANNER": "planner_mode",
    "NOESIS_LEARN_MODE": "learn_mode",
    "NOESIS_LEARN_HOME": "learn_home",
    "NOESIS_LEARN_AUTO_APPLY_MIN_SUCCESSES": "learn_auto_apply_min_successes",
    "NOESIS_LEARN_AUTO_APPLY_MIN_CONFIDENCE": "learn_auto_apply_min_confidence",
    "NOESIS_PROMPT_PROVENANCE_ENABLED": "prompt_provenance_enabled",
    "NOESIS_PROMPT_PROVENANCE_MODE": "prompt_provenance_mode",
}


def _default_toml_loader(path: Path) -> Mapping[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


@dataclass(slots=True)
class EnvTomlConfig(ConfigPort):
    """Compose environment + TOML sources into the runtime configuration."""

    __api_version__: str = "config/1.0-rc1"

    env: _EnvMap | None = None
    cwd: Path | None = None
    config_candidates: Sequence[str] | None = None
    toml_section: str = "noesis"
    toml_loader: _TomlLoader = _default_toml_loader

    def __post_init__(self) -> None:
        self._env: dict[str, str] = dict(self.env or os.environ)
        self._cwd: Path = (self.cwd or Path.cwd()).resolve()
        self._candidates: tuple[str, ...] = tuple(self.config_candidates or CONFIG_FILE_CANDIDATES)
        self._state: RuntimeConfig = default_runtime_config()
        self.reload()

    # ConfigPort interface -------------------------------------------------
    def get(self) -> ConfigSnapshot:
        return self._to_snapshot(self._state)

    def set(self, **overrides: object) -> ConfigSnapshot:
        self._state = apply_runtime_overrides(self._state, overrides)
        self._ensure_directories(self._state)
        return self._to_snapshot(self._state)

    def reload(self) -> ConfigSnapshot:
        config = default_runtime_config()

        file_overrides = self._load_file_overrides()
        if file_overrides:
            config = apply_runtime_overrides(config, file_overrides)

        env_overrides = self._load_env_overrides()
        if env_overrides:
            config = apply_runtime_overrides(config, env_overrides)

        self._state = config
        self._ensure_directories(self._state)
        return self._to_snapshot(self._state)

    def supports(self, capability: str) -> bool:
        return capability in {"reload", "env_overrides"}

    # Internal helpers -----------------------------------------------------
    def _load_file_overrides(self) -> dict[str, object]:
        path = find_config_path(self._cwd, self._candidates)
        if not path:
            return {}

        data = self.toml_loader(path)
        table = data.get(self.toml_section, data)

        if not isinstance(table, Mapping):
            raise TypeError(
                f"TOML section '{self.toml_section}' must be a mapping, got {type(table)!r}"
            )

        overrides: dict[str, object] = {}
        for key in ALLOWED_CONFIG_KEYS:
            if key in table:
                overrides[key] = table[key]
        return overrides

    def _load_env_overrides(self) -> dict[str, object]:
        overrides: dict[str, object] = {}
        for env_key, cfg_key in _ENV_KEY_MAP.items():
            if env_key in self._env:
                overrides[cfg_key] = self._env[env_key]

        if (
            "NOESIS_DIR_MIN_CONFIDENCE" in self._env
            and "direction_min_confidence" not in overrides
        ):
            warnings.warn(
                "NOESIS_DIR_MIN_CONFIDENCE is deprecated; use NOESIS_DIRECTION_MIN_CONFIDENCE",
                FutureWarning,
                stacklevel=2,
            )
            overrides["direction_min_confidence"] = self._env["NOESIS_DIR_MIN_CONFIDENCE"]

        return overrides

    @staticmethod
    def _to_snapshot(config: RuntimeConfig) -> ConfigSnapshot:
        return ConfigSnapshot(
            runs_dir=config.runs_dir,
            agents=config.agents,
            tasks=config.tasks,
            timeout_sec=config.timeout_sec,
            intuition_mode=config.intuition_mode,
            direction_min_confidence=config.direction_min_confidence,
            planner_mode=config.planner_mode,
            policy_aliases=dict(config.policy_aliases),
            learn_mode=config.learn_mode,
            learn_home=config.learn_home,
            learn_auto_apply_min_successes=config.learn_auto_apply_min_successes,
            learn_auto_apply_min_confidence=config.learn_auto_apply_min_confidence,
            prompt_provenance_enabled=config.prompt_provenance_enabled,
            prompt_provenance_mode=config.prompt_provenance_mode,
        )

    @staticmethod
    def _ensure_directories(config: RuntimeConfig) -> None:
        config.runs_dir.expanduser().mkdir(parents=True, exist_ok=True)
        config.learn_home.expanduser().mkdir(parents=True, exist_ok=True)
