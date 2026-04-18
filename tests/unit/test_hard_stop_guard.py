from __future__ import annotations

from app.services.recovery.hard_stop import HardStopDecision, RestartCounter


def test_restart_counter_enters_hard_stop_after_threshold() -> None:
    counter = RestartCounter(threshold=3)

    counter.record_restart()
    counter.record_restart()
    decision = counter.record_restart()

    assert decision == HardStopDecision(
        hard_stop=True,
        restart_count=3,
        blocked_reason="RESTART_THRESHOLD_EXCEEDED",
    )


def test_restart_counter_stays_below_hard_stop_before_threshold() -> None:
    counter = RestartCounter(threshold=3)

    decision = counter.record_restart()

    assert decision == HardStopDecision(
        hard_stop=False,
        restart_count=1,
        blocked_reason=None,
    )


def test_restart_counter_can_reset_after_successful_recovery() -> None:
    counter = RestartCounter(threshold=3)

    counter.record_restart()
    counter.record_restart()
    counter.reset()
    decision = counter.record_restart()

    assert decision == HardStopDecision(
        hard_stop=False,
        restart_count=1,
        blocked_reason=None,
    )

