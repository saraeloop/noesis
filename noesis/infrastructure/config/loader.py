"""Infrastructure adapter that loads configuration from env variables and TOML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, Sequence
import os
import tomllib
import warnings

from noesis import _config as legacy_config
from noesis.interfaces.config import ConfigPort, ConfigSnapshot

__all__ = ["EnvTomlConfig"]

_EnvMap = Mapping[str, str]
_TomlLoader = Callable[[Path], Mapping[str, object]]


def _default_toml_loader(path: Path) -> Mapping[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


@dataclass(slots=True)
class EnvTomlConfig(ConfigPort):
    """Compose environment + TOML sources into the runtime configuration."""

    env: _EnvMap | None = None
    cwd: Path | None = None
    config_candidates: Sequence[str] | None = None
    toml_section: str = "noesis"
    toml_loader: _TomlLoader = _default_toml_loader

    def __post_init__(self) -> None:
        self._env: Dict[str, str] = dict(self.env or os.environ)
        self._cwd: Path = (self.cwd or Path.cwd()).resolve()
        self._candidates: tuple[str, ...] = tuple(
            self.config_candidates or tuple(legacy_config.CONFIG_FILE_CANDIDATES)
        )
        self._allowed_keys: frozenset[str] = frozenset(legacy_config.ALLOWED_KEYS)
        self.reload()

    # ConfigPort interface -------------------------------------------------
    def get(self) -> ConfigSnapshot:
        return ConfigSnapshot.from_mapping(legacy_config.get())

    def set(self, **overrides: object) -> ConfigSnapshot:
        legacy_config.set(**overrides)
        return self.get()

    def reload(self) -> ConfigSnapshot:
        legacy_config.reset()
        file_overrides = self._load_file_overrides()
        if file_overrides:
            legacy_config.set(**file_overrides)

        env_overrides = self._load_env_overrides()
        if env_overrides:
            legacy_config.set(**env_overrides)

        return self.get()

    # Internal helpers -----------------------------------------------------
    def _load_file_overrides(self) -> Dict[str, object]:
        path = self._find_config_path()
        if not path:
            return {}

        data = self.toml_loader(path)
        table = data.get(self.toml_section, data)

        if not isinstance(table, Mapping):
            raise TypeError(
                f"TOML section '{self.toml_section}' must be a mapping, got {type(table)!r}"
            )

        overrides: Dict[str, object] = {}
        for key in self._allowed_keys:
            if key in table:
                overrides[key] = table[key]
        return overrides

    def _load_env_overrides(self) -> Dict[str, object]:
        env_map = {
            "NOESIS_RUNS_DIR": "runs_dir",
            "NOESIS_AGENTS": "agents",
            "NOESIS_TASKS": "tasks",
            "NOESIS_TIMEOUT_SEC": "timeout_sec",
            "NOESIS_INTUITION_MODE": "intuition_mode",
            "NOESIS_DIRECTION_MIN_CONFIDENCE": "direction_min_confidence",
            "NOESIS_LEARN_MODE": "learn_mode",
            "NOESIS_LEARN_HOME": "learn_home",
            "NOESIS_LEARN_AUTO_APPLY_MIN_SUCCESSES": "learn_auto_apply_min_successes",
            "NOESIS_LEARN_AUTO_APPLY_MIN_CONFIDENCE": "learn_auto_apply_min_confidence",
        }

        overrides: Dict[str, object] = {}
        for env_key, cfg_key in env_map.items():
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
            overrides["direction_min_confidence"] = self._env[
                "NOESIS_DIR_MIN_CONFIDENCE"
            ]

        return overrides

    def _find_config_path(self) -> Path | None:
        for directory in self._walk_upwards(self._cwd):
            for candidate in self._candidates:
                path = directory / candidate
                if path.is_file():
                    return path
        return None

    @staticmethod
    def _walk_upwards(start: Path) -> Iterable[Path]:
        current = start
        while True:
            yield current
            if current.parent == current:
                break
            current = current.parent
