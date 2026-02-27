from __future__ import annotations

import noesis.ports as ports


EXPECTED_PORT_EXPORTS = {
    "StateRepositoryPort",
    "EpisodeContextPort",
    "EventSinkPort",
    "EventHistoryPort",
    "PromptRecorderPort",
    "ClockPort",
    "EventIdFactoryPort",
    "EpisodeInstrumentationPorts",
}


def test_ports_public_surface_is_minimal_and_stable() -> None:
    assert set(ports.__all__) == EXPECTED_PORT_EXPORTS
    for name in ports.__all__:
        assert hasattr(ports, name), f"missing exported port symbol: {name}"
