"""
SQL guard demo package.

Provides a tiny policy illustrating how Noesis v0.4.0
verbs make safety interventions observable.
"""

from .policy import SqlGuardPolicy  # noqa: F401

__all__ = ["SqlGuardPolicy"]
