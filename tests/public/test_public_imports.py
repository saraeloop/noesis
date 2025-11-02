import importlib
import warnings

PUBLIC_IMPORTS = [
    "noesis",
    "noesis.io",
    "noesis.episode",
    "noesis.context",
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


def test_summary_deprecated_aliases_warn(monkeypatch) -> None:
    from noesis import summary

    monkeypatch.setattr(summary, "read", lambda *args, **kwargs: {})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        summary.load("missing", context=None)
    assert caught, "expected noesis.summary.load to warn"

    def _noop_finalize(**kwargs):
        return None

    monkeypatch.setattr(summary, "finalize", _noop_finalize)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        summary.finalize_summary(
            run_dir=None,
            episode_id="ep",
            task="demo",
            seed=0,
            started_at="now",
            intuition_enabled=False,
            intuition_mode=None,
            using_label=None,
            tags=None,
            intuition=None,
            schema_version="1.0.0",
            config=None,
            ports={},
        )
    assert caught, "expected noesis.summary.finalize_summary to warn"


def test_event_deprecated_alias_warns(tmp_path) -> None:
    from noesis import events

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        events.start_event(run_dir, "ep", {"task": "demo"})
    assert caught, "expected noesis.events.start_event to warn"
