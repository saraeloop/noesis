"""Core intuition abstractions for Noēsis policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ClassVar, Dict, Literal, Mapping, Optional, Protocol, TypeAlias

from .versioning import current_version, is_compatible

PolicyKind = Literal["llm", "rules", "hybrid"]

__all__ = [
    "IntuitionMode",
    "StateSnapshot",
    "IntuitionEvent",
    "PolicyKind",
    "Intuition",
    "NullIntuition",
    "HeuristicIntuition",
    "LLMIntuition",
]


class IntuitionMode(str, Enum):
    """Execution posture for an intuition policy."""

    ADVISORY = "advisory"
    INTERVENTIVE = "interventive"
    HYBRID = "hybrid"


StateSnapshot: TypeAlias = Dict[str, Any]


@dataclass(slots=True)
class IntuitionEvent:
    schema_version: ClassVar[str] = current_version("intuition")
    kind: str
    advice: str
    confidence: float
    policy_id: str = "unspecified"
    policy_version: str = "0.0.0"
    policy_kind: PolicyKind = "rules"
    applied: bool = False
    rationale: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    patch: Optional[Dict[str, Any]] = None
    target: str = "input"
    scope: str = "episode"
    blocking: bool = False

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if self.policy_kind not in ("llm", "rules", "hybrid"):
            raise ValueError(f"Invalid policy_kind '{self.policy_kind}' for IntuitionEvent")
        try:
            from noesis.domain.faculties.direction import DirectiveKind  # avoid cycle
        except Exception:
            DirectiveKind = None  # type: ignore[assignment]

        if DirectiveKind is not None:
            try:
                DirectiveKind(self.kind)
            except ValueError:
                if self.blocking:
                    self.kind = DirectiveKind.VETO.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the intuition event for persistence."""
        payload: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "advice": self.advice,
            "confidence": self.confidence,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_kind": self.policy_kind,
            "applied": self.applied,
            "rationale": self.rationale,
            "evidence_ids": list(self.evidence_ids),
            "target": self.target,
            "scope": self.scope,
            "blocking": self.blocking,
        }
        if self.patch is not None:
            payload["patch"] = dict(self.patch)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IntuitionEvent":
        """Rehydrate an intuition event from persisted artifacts."""
        version = str(payload.get("schema_version", cls.schema_version))
        if not is_compatible(version, cls.schema_version):
            raise ValueError(
                f"Incompatible intuition schema version '{version}' (expected ≤ {cls.schema_version})"
            )
        evidence_source = payload.get("evidence_ids")
        if not isinstance(evidence_source, (list, tuple)):
            evidence_source = []
        evidence_ids = [str(value) for value in evidence_source]
        policy_kind = payload.get("policy_kind", "rules")
        if policy_kind not in ("llm", "rules", "hybrid"):
            policy_kind = "rules"
        return cls(
            kind=str(payload.get("kind", "")),
            advice=str(payload.get("advice", "")),
            confidence=float(payload.get("confidence", 0.0)),
            policy_id=str(payload.get("policy_id", "unspecified")),
            policy_version=str(payload.get("policy_version", "0.0.0")),
            policy_kind=policy_kind,  # type: ignore[arg-type]
            applied=bool(payload.get("applied", False)),
            rationale=payload.get("rationale"),
            evidence_ids=evidence_ids,
            patch=payload.get("patch"),
            target=str(payload.get("target", "input")),
            scope=str(payload.get("scope", "episode")),
            blocking=bool(payload.get("blocking", False)),
        )


class Intuition(Protocol):
    mode: IntuitionMode

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        ...


class NullIntuition:
    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        return None


class HeuristicIntuition(Intuition):
    """Rule-based intuition that emits hints or patches using heuristics."""

    mode: IntuitionMode = IntuitionMode.ADVISORY

    def __init__(
        self,
        *,
        max_task_length: int = 320,
        normalize_key: str = "normalize",
        policy_id: str = "intuition.heuristic",
        policy_version: str = "1.0.0",
    ) -> None:
        self.max_task_length = max_task_length
        self.normalize_key = normalize_key
        self.policy_id = policy_id
        self.policy_version = policy_version

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        if not isinstance(state, Mapping):
            return None

        task = state.get("task")
        if isinstance(task, str) and len(task) > self.max_task_length:
            return IntuitionEvent(
                kind="hint",
                advice="Consider chunking the task input before execution.",
                confidence=0.6,
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind="rules",
                rationale="task_length",
                target="input",
                scope="episode",
            )

        normalize_value = state.get(self.normalize_key)
        if isinstance(normalize_value, bool) and normalize_value is False:
            return IntuitionEvent(
                kind="intervention",
                advice="Enable normalization prior to act phase.",
                confidence=0.7,
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind="rules",
                rationale="field_normalization",
                patch={self.normalize_key: True},
                target="input",
                scope="episode",
            )

        return None


class LLMIntuition(Intuition):
    """Wrapper that adapts callable LLM responses into IntuitionEvent."""

    mode: IntuitionMode = IntuitionMode.ADVISORY

    def __init__(
        self,
        *,
        response_provider: Optional[Callable[[StateSnapshot], Optional[Mapping[str, Any]]]] = None,
        policy_id: str = "intuition.llm",
        policy_version: str = "1.0.0",
        policy_kind: PolicyKind = "llm",
    ) -> None:
        self._provider = response_provider
        self.policy_id = policy_id
        self.policy_version = policy_version
        self.policy_kind = policy_kind

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:
        if self._provider is None:
            return None
        payload = self._provider(state)
        if not payload:
            return None

        return IntuitionEvent(
            kind=str(payload.get("kind", "hint")),
            advice=str(payload.get("advice", "")),
            confidence=float(payload.get("confidence", 0.5)),
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_kind=self.policy_kind,
            rationale=payload.get("rationale"),
            evidence_ids=list(payload.get("evidence_ids", [])),
            patch=payload.get("patch"),
            target=str(payload.get("target", "input")),
            scope=str(payload.get("scope", "episode")),
            blocking=bool(payload.get("blocking", False)),
        )
