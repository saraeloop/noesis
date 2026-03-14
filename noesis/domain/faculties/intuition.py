"""Core intuition abstractions for Noesis policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ClassVar, Dict, Literal, Mapping, Optional, Protocol, Sequence, TypeAlias

from .versioning import current_version, is_compatible

PolicyKind = Literal["llm", "rules", "hybrid"]

__all__ = [
    "IntuitionMode",
    "RiskLevel",
    "ScrutinyLevel",
    "SalienceSignal",
    "StrategyHint",
    "ToolConstraint",
    "StateSnapshot",
    "IntuitionEvent",
    "IntuitionAssessment",
    "derive_intuition_assessment",
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


class RiskLevel(str, Enum):
    """Risk posture surfaced by intuition for downstream steering."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ScrutinyLevel(str, Enum):
    """Review intensity expected from downstream planning and governance."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    STRICT = "strict"


class SalienceSignal(str, Enum):
    """Typed upstream cues that Direction can prioritize explicitly."""

    TASK_COMPLEXITY = "task_complexity"
    NORMALIZATION_GAP = "normalization_gap"
    POLICY_HINT = "policy_hint"
    SAFETY_BOUNDARY = "safety_boundary"


class StrategyHint(str, Enum):
    """Planning postures that Intuition can suggest to Direction."""

    CONSERVATIVE = "conservative"
    VERIFY_FIRST = "verify_first"
    RETRIEVE_MORE = "retrieve_more"
    NARROW_SCOPE = "narrow_scope"


class ToolConstraint(str, Enum):
    """Tool-use constraints that Direction can apply explicitly."""

    NO_SIDE_EFFECTS = "no_side_effects"
    READ_ONLY = "read_only"
    REQUIRE_DOUBLE_CHECK = "require_double_check"


StateSnapshot: TypeAlias = Dict[str, Any]


@dataclass(frozen=True, slots=True)
class IntuitionAssessment:
    """Minimal typed steering contract consumed by Direction."""

    risk_level: RiskLevel
    salience_signals: tuple[SalienceSignal, ...] = ()
    strategy_hints: tuple[StrategyHint, ...] = ()
    tool_constraints: tuple[ToolConstraint, ...] = ()
    scrutiny_level: ScrutinyLevel = ScrutinyLevel.NORMAL
    evidence_ids: tuple[str, ...] = ()


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
    risk_level: RiskLevel | None = None
    salience_signals: tuple[SalienceSignal, ...] = ()
    strategy_hints: tuple[StrategyHint, ...] = ()
    tool_constraints: tuple[ToolConstraint, ...] = ()
    scrutiny_level: ScrutinyLevel | None = None

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
        if self.risk_level is not None and not isinstance(self.risk_level, RiskLevel):
            self.risk_level = RiskLevel(str(self.risk_level))
        if self.scrutiny_level is not None and not isinstance(self.scrutiny_level, ScrutinyLevel):
            self.scrutiny_level = ScrutinyLevel(str(self.scrutiny_level))
        self.salience_signals = _coerce_enum_sequence(self.salience_signals, SalienceSignal)
        self.strategy_hints = _coerce_enum_sequence(self.strategy_hints, StrategyHint)
        self.tool_constraints = _coerce_enum_sequence(self.tool_constraints, ToolConstraint)

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
        if self.risk_level is not None:
            payload["risk_level"] = self.risk_level.value
        if self.salience_signals:
            payload["salience_signals"] = [signal.value for signal in self.salience_signals]
        if self.strategy_hints:
            payload["strategy_hints"] = [hint.value for hint in self.strategy_hints]
        if self.tool_constraints:
            payload["tool_constraints"] = [constraint.value for constraint in self.tool_constraints]
        if self.scrutiny_level is not None:
            payload["scrutiny_level"] = self.scrutiny_level.value
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
            risk_level=_coerce_optional_enum(payload.get("risk_level"), RiskLevel),
            salience_signals=_coerce_enum_sequence(payload.get("salience_signals"), SalienceSignal),
            strategy_hints=_coerce_enum_sequence(payload.get("strategy_hints"), StrategyHint),
            tool_constraints=_coerce_enum_sequence(payload.get("tool_constraints"), ToolConstraint),
            scrutiny_level=_coerce_optional_enum(payload.get("scrutiny_level"), ScrutinyLevel),
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
                risk_level=RiskLevel.MODERATE,
                salience_signals=(SalienceSignal.TASK_COMPLEXITY,),
                strategy_hints=(StrategyHint.RETRIEVE_MORE, StrategyHint.NARROW_SCOPE),
                scrutiny_level=ScrutinyLevel.ELEVATED,
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
                risk_level=RiskLevel.MODERATE,
                salience_signals=(SalienceSignal.NORMALIZATION_GAP,),
                strategy_hints=(StrategyHint.VERIFY_FIRST,),
                tool_constraints=(ToolConstraint.REQUIRE_DOUBLE_CHECK,),
                scrutiny_level=ScrutinyLevel.ELEVATED,
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
            risk_level=_coerce_optional_enum(payload.get("risk_level"), RiskLevel),
            salience_signals=_coerce_enum_sequence(payload.get("salience_signals"), SalienceSignal),
            strategy_hints=_coerce_enum_sequence(payload.get("strategy_hints"), StrategyHint),
            tool_constraints=_coerce_enum_sequence(payload.get("tool_constraints"), ToolConstraint),
            scrutiny_level=_coerce_optional_enum(payload.get("scrutiny_level"), ScrutinyLevel),
        )


def derive_intuition_assessment(event: IntuitionEvent) -> IntuitionAssessment:
    """Derive the canonical runtime steering contract from an intuition event."""

    risk_level = event.risk_level or _default_risk_level(event)
    scrutiny_level = event.scrutiny_level or _default_scrutiny_level(event)
    salience_signals = event.salience_signals or _default_salience_signals(event)
    strategy_hints = event.strategy_hints or _default_strategy_hints(event)
    tool_constraints = event.tool_constraints or _default_tool_constraints(event)
    return IntuitionAssessment(
        risk_level=risk_level,
        salience_signals=salience_signals,
        strategy_hints=strategy_hints,
        tool_constraints=tool_constraints,
        scrutiny_level=scrutiny_level,
        evidence_ids=tuple(event.evidence_ids),
    )


def _coerce_enum_sequence(values: object, enum_type: type[Enum]) -> tuple[Enum, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    result: list[Enum] = []
    for value in values:
        if isinstance(value, enum_type):
            result.append(value)
            continue
        try:
            result.append(enum_type(str(value)))
        except ValueError:
            continue
    return tuple(result)


def _coerce_optional_enum(value: object, enum_type: type[Enum]) -> Enum | None:
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError:
        return None


def _default_risk_level(event: IntuitionEvent) -> RiskLevel:
    if event.blocking or event.kind == "veto":
        return RiskLevel.CRITICAL
    if event.kind == "intervention":
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _default_scrutiny_level(event: IntuitionEvent) -> ScrutinyLevel:
    if event.blocking or event.kind == "veto":
        return ScrutinyLevel.STRICT
    if event.kind == "intervention":
        return ScrutinyLevel.ELEVATED
    return ScrutinyLevel.NORMAL


def _default_salience_signals(event: IntuitionEvent) -> tuple[SalienceSignal, ...]:
    if event.kind in {"hint", "intervention"}:
        return (SalienceSignal.POLICY_HINT,)
    if event.blocking or event.kind == "veto":
        return (SalienceSignal.SAFETY_BOUNDARY,)
    return ()


def _default_strategy_hints(event: IntuitionEvent) -> tuple[StrategyHint, ...]:
    if event.blocking or event.kind == "veto":
        return (StrategyHint.CONSERVATIVE, StrategyHint.VERIFY_FIRST)
    if event.kind == "intervention":
        return (StrategyHint.VERIFY_FIRST,)
    return ()


def _default_tool_constraints(event: IntuitionEvent) -> tuple[ToolConstraint, ...]:
    if event.blocking or event.kind == "veto":
        return (ToolConstraint.NO_SIDE_EFFECTS, ToolConstraint.REQUIRE_DOUBLE_CHECK)
    return ()
