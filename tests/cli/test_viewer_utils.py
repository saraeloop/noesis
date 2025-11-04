from noesis.cli.viewer import _clamp_phase_ms


def test_clamp_phase_ms_rounds_and_clamps() -> None:
    metrics = {"phase_ms": {"plan": 0.4, "act": 1.2, "reflect": 0}}
    out = _clamp_phase_ms(metrics)
    assert out["plan"] == 1
    assert out["act"] == 1
    assert out["reflect"] == 0
