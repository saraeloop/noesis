from __future__ import annotations

import importlib
import warnings


def test_config_shim_warns_once(monkeypatch):
    monkeypatch.delenv("NOESIS_DIR_MIN_CONFIDENCE", raising=False)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        importlib.import_module("noesis.config")
        importlib.reload(importlib.import_module("noesis.config"))
    future_warnings = [msg for msg in w if msg.category is FutureWarning]
    assert len(future_warnings) == 1
    assert "legacy" in str(future_warnings[0].message)
