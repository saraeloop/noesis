from __future__ import annotations

from contextlib import contextmanager

import pytest

from noesis.infrastructure.actuation.dispatcher import invoke_executor, resolve_executor
from noesis.runtime.actuation_registry import get_actuation_registry


@contextmanager
def _preserve_registry():
    registry = get_actuation_registry()
    original_shell = registry.shell_executor
    original_adapter = registry.adapter_executor
    try:
        yield registry
    finally:
        registry.shell_executor = original_shell
        registry.adapter_executor = original_adapter


def test_resolve_executor_uses_configured_shell_executor() -> None:
    with _preserve_registry() as registry:
        registry.shell_executor = lambda **payload: {"seen": payload}
        dispatcher = resolve_executor("shell")

        result = dispatcher({"command": "echo ok"})

    assert result == {"seen": {"command": "echo ok"}}


def test_resolve_executor_requires_configured_executor() -> None:
    with _preserve_registry() as registry:
        registry.shell_executor = None

        with pytest.raises(ValueError, match="shell executor is not configured"):
            resolve_executor("shell")


def test_invoke_executor_falls_back_to_payload_argument() -> None:
    def payload_only(payload):
        return {"seen": payload}

    result = invoke_executor(payload_only, {"command": "echo ok"})

    assert result == {"seen": {"command": "echo ok"}}
