from __future__ import annotations

import types
import sys

import noesis as ns

from noesis.context import create_runtime_context
from noesis.runtime.port_loader import instantiate_port, merge_port_specs


def _install_dummy_module(monkeypatch, name: str, cls) -> None:
    module = types.ModuleType(name)
    setattr(module, cls.__name__, cls)
    monkeypatch.setitem(sys.modules, name, module)


def test_instantiate_port_literal(monkeypatch):
    class DummyMemory:
        __api_version__ = "memory/1.0-rc1"

        def __init__(self, path: str) -> None:
            self.path = path

        def supports(self, capability: str) -> bool:
            return capability == "query"

        def write_fact(self, fact):
            raise NotImplementedError

        def query(self, query, *, k: int = 5):
            return []

        def link_episode(self, episode_id: str, fact_ids):
            return None

    module_name = "tests.runtime.dummy_ports"
    _install_dummy_module(monkeypatch, module_name, DummyMemory)

    provider, api = instantiate_port(f"{module_name}:DummyMemory?path='store'")
    assert api == "memory/1.0-rc1"
    assert provider.path == "store"
    assert provider.supports("query")


def test_merge_port_precedence():
    entry = {"memory": "mod:Entry"}
    config = {"memory": "mod:Config", "insight": "mod:ConfigInsight"}
    cli = {"memory": "mod:Cli"}
    merged = merge_port_specs(entry, config, cli)
    assert merged == {"memory": "mod:Cli", "insight": "mod:ConfigInsight"}


def test_runtime_context_lists_ports(tmp_path):
    ns.set(runs_dir=str(tmp_path / "runs"))
    runtime_context = create_runtime_context()
    ports = runtime_context.list_ports()
    assert "config" in ports
    episode_id = ns.run(task="port summary", intuition=False, context=runtime_context)
    summary = ns.summary.read(episode_id, context=runtime_context)
    assert summary.get("ports", {}).get("config") == ports["config"]
