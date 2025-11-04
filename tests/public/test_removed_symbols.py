import importlib
import sys

import pytest

from noesis.deprecated import iter_removed_symbols


@pytest.mark.parametrize("symbol", iter_removed_symbols())
def test_removed_symbols_unavailable(monkeypatch: pytest.MonkeyPatch, symbol) -> None:
    monkeypatch.delenv("NOESIS_LEGACY_SHIMS", raising=False)
    if "noesis.deprecated" in sys.modules:
        importlib.reload(sys.modules["noesis.deprecated"])

    if symbol.module_removed:
        sys.modules.pop(symbol.fq_name, None)
        with pytest.raises(ImportError):
            importlib.import_module(symbol.fq_name)
        return

    sys.modules.pop(symbol.module, None)
    module = importlib.import_module(symbol.module)
    with pytest.raises(AttributeError):
        getattr(module, symbol.symbol)
