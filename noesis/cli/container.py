from __future__ import annotations

from typing import Sequence

from noesis.runtime.config_provider import RuntimeContainer, create_runtime_container, get_config_port
from noesis.runtime.port_loader import (
    build_container_from_sources,
    discover_entrypoint_ports,
    load_toml_port_specs,
)


def build_cli_container(port_specs: Sequence[str] | None = None) -> RuntimeContainer:
    config_provider = get_config_port()
    config_ports = load_toml_port_specs()
    entry_ports = discover_entrypoint_ports()
    return build_container_from_sources(
        config_port=config_provider,
        cli_specs=port_specs,
        config_specs=config_ports,
        entrypoint_specs=entry_ports,
    )
