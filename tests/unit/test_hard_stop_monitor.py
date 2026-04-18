from __future__ import annotations

from app.services.risk.hard_stop import HardStopDecision, HardStopMonitor
from app.services.risk.stop_loss import PositionSnapshot


def test_hard_stop_monitor_generates_stop_loss_order_when_price_hits_threshold() -> None:
    monitor = HardStopMonitor()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = monitor.evaluate(position=position, current_price=805.0)

    assert decision == HardStopDecision(
        triggered=True,
        order_side="sell",
        quantity=190.5,
        trigger_price=805.0,
        reason_code="STOP_LOSS_PRICE_HIT",
        is_stop_loss=True,
    )


def test_hard_stop_monitor_does_not_trigger_above_stop_loss_price() -> None:
    monitor = HardStopMonitor()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=810.0,
        quantity=100.0,
        stop_loss_price=800.28,
        stop_loss_pct=0.012,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = monitor.evaluate(position=position, current_price=801.0)

    assert decision == HardStopDecision(
        triggered=False,
        order_side="sell",
        quantity=0.0,
        trigger_price=801.0,
        reason_code=None,
        is_stop_loss=False,
    )

