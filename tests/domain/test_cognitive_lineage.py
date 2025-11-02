from datetime import datetime, timedelta, timezone
from uuid import uuid4

from noesis.domain.state import CognitiveEvent, CognitiveMetrics, CognitiveVerb, LineageTracker


def _metrics(duration_ms: float = 1.0) -> CognitiveMetrics:
    started = datetime.now(timezone.utc)
    completed = started + timedelta(milliseconds=duration_ms)
    return CognitiveMetrics(started_at=started, completed_at=completed, duration_ms=duration_ms)


def test_lineage_tracker_links_events() -> None:
    tracker = LineageTracker()
    first = CognitiveEvent(episode_id="ep", verb=CognitiveVerb.OBSERVE, payload={},).with_metrics(_metrics())
    linked_first = tracker.register(first)
    second = CognitiveEvent(episode_id="ep", verb=CognitiveVerb.INTERPRET, payload={},).with_metrics(_metrics())
    linked_second = tracker.register(second)

    assert linked_second.caused_by == linked_first.event_id
    assert tracker.coverage() == 0.5


def test_lineage_tracker_seeding_uses_existing_event() -> None:
    tracker = LineageTracker()
    seed_id = uuid4()
    tracker.seed(last_event_id=seed_id)
    event = CognitiveEvent(episode_id="ep", verb=CognitiveVerb.PLAN, payload={},).with_metrics(_metrics())
    linked = tracker.register(event)

    assert linked.caused_by == seed_id
    assert linked.event_id != seed_id
