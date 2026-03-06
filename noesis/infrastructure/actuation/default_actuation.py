"""Compatibility wrappers for the canonical governed actuation runtime."""

from __future__ import annotations

from typing import Any

from noesis.context import RuntimeContext
from noesis.interfaces.actuation import ActuationPort, GovernedActRequest


class DefaultActuationPort(ActuationPort):
    """Compatibility port that forwards governed actions to the canonical runtime."""

    __api_version__ = "actuation/1.0"

    def governed_act(self, request: GovernedActRequest, *, context: RuntimeContext) -> Any:
        return governed_act_impl(request=request, context=context)


def governed_act_impl(*, request: GovernedActRequest, context: RuntimeContext) -> Any:
    """
    Forward governed actuation to the canonical core runtime entrypoint.

    This module intentionally owns no governance, orchestration, finalization,
    sealing, or artifact-writing behavior.
    """
    from noesis.core import governed_act as core_governed_act

    return core_governed_act(
        goal=request.goal,
        kind=request.kind,
        payload=dict(request.payload),
        seed=request.seed,
        tags=dict(request.tags) if request.tags else None,
        context=context,
        provenance=dict(request.provenance) if request.provenance else None,
        risk_tags=tuple(request.risk_tags) if request.risk_tags else None,
        redaction=dict(request.redaction) if request.redaction else None,
        determinism=request.determinism,
    )


__all__ = ["DefaultActuationPort", "governed_act_impl"]
