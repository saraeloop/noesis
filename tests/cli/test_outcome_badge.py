from __future__ import annotations

from noesis.cli.theme import outcome_badge, normalize_outcome


def test_outcome_badge_known_values() -> None:
    badge = outcome_badge("success")
    assert badge.label == "SUCCESS"
    assert badge.style == "ok"

    badge = outcome_badge("success_unverified")
    assert badge.label == "UNVERIFIED"
    assert badge.style == "warn"

    badge = outcome_badge("goal_not_achieved")
    assert badge.label == "GOAL NOT ACHIEVED"
    assert badge.style == "err"

    badge = outcome_badge("violated")
    assert badge.label == "VIOLATED"
    assert badge.style == "err"


def test_outcome_badge_unknown() -> None:
    badge = outcome_badge("n/a")
    assert badge.label == "UNKNOWN"
    assert badge.style == "muted"


def test_normalize_outcome_fallbacks() -> None:
    assert normalize_outcome(None, status="vetoed") == "violated"
    assert normalize_outcome(None, status="error") == "error"
    assert normalize_outcome(None, success=True) == "success"
    assert normalize_outcome(None, success=False) == "error"
