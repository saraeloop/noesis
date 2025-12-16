import importlib
import sys
import warnings

import pytest

PUBLIC_IMPORTS = [
    "noesis",
    "noesis.io",
    "noesis.episode",
    "noesis.context",
    "noesis.ports",
    "noesis.trace",
    "noesis.events",
    "noesis.summary",
    "noesis.runtime",
    "noesis.runtime.events",
    "noesis.runtime.summary",
    "noesis.runtime.learning",
    "noesis.runtime.utils",
    "noesis.intuition",
    "noesis.direction",
    "noesis.governance",
    "noesis.learn",
    "noesis.insight",
    "noesis.adapters",
]


def test_supported_imports_do_not_warn() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", DeprecationWarning)
        for target in PUBLIC_IMPORTS:
            module = importlib.import_module(target)
            assert module is not None
    assert not caught, "expected no DeprecationWarning when importing public surface"


def test_root_import_smoke() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", DeprecationWarning)
        import noesis

        assert hasattr(noesis, "run")
        assert hasattr(noesis, "events")
        assert hasattr(noesis, "summary")
        assert hasattr(noesis, "context")
    assert not caught


def test_legacy_root_exports_warn() -> None:
    import noesis

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        # Access without call should still warn thanks to module __getattr__
        _ = noesis.RuntimeContext
    assert caught, "expected accessing legacy alias to warn"


def _reload(module_name: str):
    module = importlib.import_module(module_name)
    return importlib.reload(module)


def _reset_deprecated(monkeypatch: pytest.MonkeyPatch, *, legacy: bool) -> None:
    if legacy:
        monkeypatch.setenv("NOESIS_LEGACY_SHIMS", "1")
    else:
        monkeypatch.delenv("NOESIS_LEGACY_SHIMS", raising=False)
    if "noesis.deprecated" in sys.modules:
        importlib.reload(sys.modules["noesis.deprecated"])


@pytest.fixture(autouse=True)
def restore_default_environment(monkeypatch: pytest.MonkeyPatch):
    yield
    monkeypatch.delenv("NOESIS_LEGACY_SHIMS", raising=False)
    if "noesis.deprecated" in sys.modules:
        importlib.reload(sys.modules["noesis.deprecated"])
    for module_name in ("noesis.summary", "noesis.events"):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


def test_summary_legacy_aliases_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_deprecated(monkeypatch, legacy=False)
    summary = _reload("noesis.summary")
    assert not hasattr(summary, "load")
    assert not hasattr(summary, "finalize_summary")


def test_events_legacy_aliases_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_deprecated(monkeypatch, legacy=False)
    events = _reload("noesis.events")
    for attr in (
        "start_event",
        "observe_event",
        "interpret_event",
        "plan_event",
        "act_event",
        "reflect_event",
        "direction_event",
        "ensure_act_event",
        "terminate_event",
    ):
        assert not hasattr(events, attr), f"expected {attr} to be removed"


def test_state_store_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_deprecated(monkeypatch, legacy=False)
    with pytest.raises(ImportError):
        importlib.import_module("noesis.state.store")


def test_legacy_env_re_enables_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_deprecated(monkeypatch, legacy=True)
    summary = _reload("noesis.summary")
    assert callable(summary.load)
    assert callable(summary.finalize_summary)


def test_legacy_env_re_enables_events(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_deprecated(monkeypatch, legacy=True)
    events = _reload("noesis.events")
    assert callable(events.start_event)
    assert callable(events.terminate_event)
