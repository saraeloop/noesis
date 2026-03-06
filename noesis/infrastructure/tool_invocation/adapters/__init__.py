"""Concrete protocol adapters for prepared tool invocation dispatch."""

from .subprocess_adapter import SubprocessToolInvocationAdapter

__all__ = ["SubprocessToolInvocationAdapter"]
