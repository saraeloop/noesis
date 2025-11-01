"""Utility helpers for loading runtime ports from specs and plugins."""

from __future__ import annotations

import ast
import importlib
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple
from urllib.parse import parse_qsl

import tomllib

from noesis.domain.config import CONFIG_FILE_CANDIDATES
from noesis.infrastructure.config.utils import find_config_path
from noesis.runtime.config_provider import RuntimeContainer, create_runtime_container

PORT_ENTRYPOINT_GROUP = "noesis.plugins"


def parse_assignment(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Port specification must be name=spec, got {value!r}")
    name, spec = value.split("=", 1)
    name = name.strip()
    spec = spec.strip()
    if not name or not spec:
        raise ValueError(f"Invalid port specification {value!r}")
    return name, spec


def _parse_kwargs(query: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if not query:
        return params
    for key, raw_value in parse_qsl(query, keep_blank_values=False):
        if not key:
            raise ValueError("Empty parameter key in port spec.")
        try:
            params[key] = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Invalid literal for parameter '{key}': {raw_value!r}") from exc
    return params


def instantiate_port(spec: str) -> Tuple[Any, str]:
    target, sep, query = spec.partition("?")
    module_name, colon, attr = target.partition(":")
    if not colon or not attr:
        raise ValueError(f"Port spec must be 'module:Class', got {spec!r}")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    kwargs = _parse_kwargs(query)
    provider = factory(**kwargs) if callable(factory) else factory  # type: ignore[misc]
    api = getattr(provider, "__api_version__", None)
    if not isinstance(api, str):
        raise ValueError(f"Port {spec!r} does not declare '__api_version__'")
    return provider, api


def discover_entrypoint_ports() -> Dict[str, str]:
    ports: Dict[str, str] = {}
    try:
        entry_points = metadata.entry_points()
        selected = entry_points.select(group=PORT_ENTRYPOINT_GROUP)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - metadata compatibility
        selected = ()
    for entry in selected:
        ports[entry.name] = entry.value
    return ports


def merge_port_specs(*spec_sources: Mapping[str, str]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for source in spec_sources:
        merged.update(source)
    return merged


def load_ports(specs: Mapping[str, str]) -> Dict[str, Tuple[Any, str]]:
    loaded: Dict[str, Tuple[Any, str]] = {}
    for name, spec in specs.items():
        provider, api = instantiate_port(spec)
        loaded[name] = (provider, api)
    return loaded


def build_container_from_sources(
    *,
    config_port=None,
    cli_specs: Sequence[str] | None = None,
    config_specs: Mapping[str, str] | None = None,
    entrypoint_specs: Mapping[str, str] | None = None,
) -> RuntimeContainer:
    cli_map = dict(parse_assignment(spec) for spec in (cli_specs or []))
    config_map = dict(config_specs or {})
    entry_map = dict(entrypoint_specs or {})
    merged_specs = merge_port_specs(entry_map, config_map, cli_map)
    loaded_ports = load_ports(merged_specs)
    return create_runtime_container(config_port=config_port, ports=loaded_ports)


def load_toml_port_specs() -> Dict[str, str]:
    path: Path | None = find_config_path(Path.cwd(), CONFIG_FILE_CANDIDATES)
    if not path:
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    table = data.get("noesis", {})
    ports = {}
    for source in (table.get("ports"), data.get("ports")):
        if isinstance(source, Mapping):
            ports.update({str(k): str(v) for k, v in source.items()})
    return ports
