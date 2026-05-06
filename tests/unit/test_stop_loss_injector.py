from __future__ import annotations

from app.services.risk.stop_loss import (
    BuyExecutionAlertPayload,
    PositionSnapshot,
    StopLossInjector,
)


def test_stop_loss_injector_creates_position_snapshot_on_buy_fill() -> None:
    injector = StopLossInjector(
        stop_loss_by_signal={
            "weak": 0.008,
            "medium": 0.030,
            "strong": 0.030,
            "very_strong": 0.022,
        },
        validation_window_sec=180,
        min_expected_return_pct=0.004,
    )

    position = injector.inject(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
    )

    assert position == PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=795.4,
        stop_loss_pct=0.030,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )


def test_buy_alert_payload_includes_stop_loss_price() -> None:
    injector = StopLossInjector(
        stop_loss_by_signal={
            "weak": 0.008,
            "medium": 0.030,
            "strong": 0.030,
            "very_strong": 0.022,
        },
        validation_window_sec=180,
        min_expected_return_pct=0.004,
    )
    position = injector.inject(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=810.0,
        quantity=100.0,
    )

    payload = injector.build_buy_alert_payload(
        position,
        buy_amount=81000.0,
        buy_ratio=0.18,
        executed_at="2026-04-18T10:15:00+09:00",
    )

    assert payload == BuyExecutionAlertPayload(
        market="KRW-XRP",
        signal_level="medium",
        buy_amount=81000.0,
        quantity=100.0,
        buy_ratio=0.18,
        entry_price=810.0,
        stop_loss_price=785.7,
        executed_at="2026-04-18T10:15:00+09:00",
    )
