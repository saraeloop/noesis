import time

from noesis.domain.state import CognitiveVerb
from noesis.runtime.clock import RuntimeClock


def test_runtime_clock_records_positive_duration() -> None:
    clock = RuntimeClock()
    token = clock.start(CognitiveVerb.ACT)
    time.sleep(0.005)
    metrics = clock.stop(token)

    assert metrics.duration_ms > 0
    assert metrics.completed_at >= metrics.started_at
