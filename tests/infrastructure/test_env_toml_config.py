from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pytest

from noesis.infrastructure.config import EnvTomlConfig


def test_env_overrides_toml(tmp_path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        "[noesis]\nruns_dir = \"from-toml\"\ndirection_min_confidence = 0.65\n",
        encoding="utf-8",
    )

    env: Mapping[str, str] = {
        "NOESIS_DIRECTION_MIN_CONFIDENCE": "0.9",
    }

    provider = EnvTomlConfig(
        env=env,
        cwd=tmp_path,
        config_candidates=("custom.toml",),
    )

    snapshot = provider.get()
    assert snapshot.runs_dir.name == "from-toml"
    assert pytest.approx(snapshot.direction_min_confidence, rel=1e-6) == 0.9

    override_dir = tmp_path / "manual-runs"
    updated = provider.set(runs_dir=str(override_dir))
    assert updated.runs_dir == override_dir
    assert updated.direction_min_confidence == snapshot.direction_min_confidence


def test_toml_section_requires_mapping(tmp_path):
    config_path = tmp_path / "broken.toml"
    config_path.write_text("invalid = 1\n", encoding="utf-8")

    def fake_loader(path: Path):
        return {"noesis": ["not", "a", "mapping"]}

    with pytest.raises(TypeError):
        EnvTomlConfig(
            env={},
            cwd=tmp_path,
            config_candidates=("broken.toml",),
            toml_loader=fake_loader,
        )
