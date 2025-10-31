from __future__ import annotations

import importlib
import sys


def test_noesis_toml_overrides(tmp_path, monkeypatch):
    cfg = tmp_path / "noesis.toml"
    cfg.write_text("runs_dir = \"logs\"\ndirection_min_confidence = 0.75\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    for name in list(sys.modules):
        if name.startswith("noesis"):
            sys.modules.pop(name, None)

    importlib.import_module("noesis")
    from noesis import _config as cfg_module

    settings = cfg_module.get()
    assert settings["runs_dir"].endswith("logs")
    assert settings["direction_min_confidence"] == 0.75
