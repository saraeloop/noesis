from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping, Sequence

from noesis.context import RuntimeContext
from noesis.exceptions import NoesisVeto


def governed_act(
    *,
    goal: str,
    kind: str,
    payload: Mapping[str, Any],
    seed: int = 0,
    tags: Mapping[str, Any] | None = None,
    context: Any | None = None,
    provenance: Mapping[str, Any] | None = None,
    risk_tags: Sequence[str] | None = None,
    redaction: Mapping[str, Any] | None = None,
) -> Any:
    """Execute a governed action through the public API."""
    runtime_context: RuntimeContext
    merged_tags = tags
    determinism = None
    if context is None:
        session_provider = import_module("noesis").session_provider
        session = session_provider().current()
        runtime_context = session.context
        merged_tags = session.merge_tags(tags)
        determinism = getattr(session, "determinism", None)
    elif hasattr(context, "context") and hasattr(context, "merge_tags"):
        session = context
        runtime_context = session.context
        merged_tags = session.merge_tags(tags)
        determinism = getattr(session, "determinism", None)
    else:
        runtime_context = context

    require_actuation_port = import_module("noesis._internal.actuation").require_actuation_port
    port = require_actuation_port(runtime_context)
    request_cls = import_module("noesis.interfaces.actuation").GovernedActRequest
    request = request_cls(
        goal=goal,
        kind=kind,
        payload=dict(payload),
        seed=seed,
        tags=dict(merged_tags) if merged_tags else None,
        provenance=dict(provenance) if provenance else None,
        risk_tags=tuple(risk_tags) if risk_tags else None,
        redaction=dict(redaction) if redaction else None,
        determinism=determinism,
    )
    try:
        return port.governed_act(request, context=runtime_context)
    except NoesisVeto:
        raise
    except Exception as exc:  # noqa: BLE001
        if _is_veto_like(exc):
            raise _normalize_veto(exc, fallback_target=kind) from exc
        raise


__all__ = ["governed_act"]


def _is_veto_like(exc: Exception) -> bool:
    return hasattr(exc, "advice") or hasattr(exc, "scope")


def _normalize_veto(exc: Exception, *, fallback_target: str) -> NoesisVeto:
    return NoesisVeto(
        advice=getattr(exc, "advice", str(exc)),
        target=getattr(exc, "target", fallback_target),
        scope=getattr(exc, "scope", "governance.pre_act"),
        decision=getattr(exc, "decision", None),
        rule_id=getattr(exc, "rule_id", None),
        policy_id=getattr(exc, "policy_id", None),
        policy_version=getattr(exc, "policy_version", None),
        policy_kind=getattr(exc, "policy_kind", None),
        enforced=getattr(exc, "enforced", None),
        details=getattr(exc, "details", None),
        error=getattr(exc, "error", None),
        governance_id=getattr(exc, "governance_id", None),
        action_candidate_id=getattr(exc, "action_candidate_id", None),
    )
