"""Typed errors for protocol-first tool contract use cases."""

from __future__ import annotations


class ToolContractError(RuntimeError):
    """Base class for tool-contract errors."""


class ToolAuthenticationError(ToolContractError):
    """Authentication failed for a tool invocation."""


class ToolAuthorizationError(ToolContractError):
    """Authorization failed for a tool invocation."""


class PreparedToolInvocationNotFoundError(ToolContractError):
    """No prepared invocation exists for the requested run/draft identity."""


class AmbiguousPreparedToolInvocationError(ToolContractError):
    """More than one pending prepared invocation exists for the requested run."""


class ApprovalDecisionRequiredError(ToolContractError):
    """Execution requires an approval decision that was not found or approved."""


class ApprovalDecisionBindingError(ToolContractError):
    """Approval decision does not match the reviewed prepared intent."""


class UnsupportedToolProtocolError(ToolContractError):
    """The requested tool protocol is not supported by the current runtime bridge."""


__all__ = [
    "AmbiguousPreparedToolInvocationError",
    "ApprovalDecisionBindingError",
    "ApprovalDecisionRequiredError",
    "PreparedToolInvocationNotFoundError",
    "ToolAuthenticationError",
    "ToolAuthorizationError",
    "ToolContractError",
    "UnsupportedToolProtocolError",
]
