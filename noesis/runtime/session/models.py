"""Typed configuration inputs used to build `NoesisSession` instances."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, TYPE_CHECKING, Optional

from noesis.context import RuntimeContext, create_runtime_context
from noesis.infrastructure.config import EnvTomlConfig
from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG

if TYPE_CHECKING:
    from .session import NoesisSession

__all__ = ["SessionConfig", "SessionBuilder", "DeterminismConfig"]


@dataclass(slots=True, frozen=True)
class DeterminismConfig:
    """Optional deterministic instrumentation injected into a session run."""

    clock: DeterministicClock
    rng: DeterministicRNG
    episode_timestamp_ms: Optional[int] = None


@dataclass(slots=True, frozen=True)
class SessionConfig:
    """
    Immutable snapshot of session-level defaults.

    Stores the underlying configuration snapshot plus author-supplied default
    tags that should be attached to every run initiated through the session.
    """

    snapshot: ConfigSnapshot
    default_tags: Mapping[str, Any] = field(default_factory=dict)
    determinism: Optional[DeterminismConfig] = None

    @property
    def runs_dir(self) -> Path:
        return self.snapshot.runs_dir

    @property
    def planner_mode(self) -> str:
        return self.snapshot.planner_mode.value

    def merge_tags(self, tags: Mapping[str, Any] | None) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(self.default_tags)
        if tags:
            merged.update(tags)
        return merged


@dataclass(slots=True)
class SessionBuilder:
    """
    Helper for constructing `NoesisSession` instances with explicit dependencies.
    """

    config_port: ConfigPort = field(default_factory=EnvTomlConfig)
    default_tags: MutableMapping[str, Any] = field(default_factory=dict)
    ports: MutableMapping[str, tuple[Any, str]] = field(default_factory=dict)
    determinism: Optional[DeterminismConfig] = None

    @classmethod
    def from_env(cls) -> "SessionBuilder":
        """Build a session builder that sources config from env/TOML."""
        return cls(config_port=EnvTomlConfig())

    def with_port(self, name: str, provider: Any, *, api: str) -> "SessionBuilder":
        """Register an adapter to be bound when the session is built."""
        if not name:
            raise ValueError("Port name must be provided")
        self.ports[name] = (provider, api)
        return self

    def with_default_tags(self, **tags: Any) -> "SessionBuilder":
        """Attach default tags applied to every run executed via the session."""
        self.default_tags.update(tags)
        return self

    def with_determinism(
        self,
        *,
        clock: DeterministicClock,
        rng: DeterministicRNG,
        episode_timestamp_ms: Optional[int] = None,
    ) -> "SessionBuilder":
        """Attach deterministic instrumentation for reproducible runs."""
        self.determinism = DeterminismConfig(clock=clock, rng=rng, episode_timestamp_ms=episode_timestamp_ms)
        return self

    def build(self) -> "NoesisSession":
        """Materialize a new NoesisSession with the collected dependencies."""
        from .session import NoesisSession

        context = create_runtime_context(config_port=self.config_port, ports=dict(self.ports))
        snapshot = self.config_port.get()
        config = SessionConfig(
            snapshot=snapshot,
            default_tags=dict(self.default_tags),
            determinism=self.determinism,
        )
        return NoesisSession(config=config, context=context)
