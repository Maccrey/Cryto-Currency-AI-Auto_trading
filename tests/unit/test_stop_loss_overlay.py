from __future__ import annotations

from app.services.dashboard.overlay import StopLossOverlay, StopLossOverlayService
from app.services.risk.stop_loss import PositionSnapshot


def test_stop_loss_overlay_service_returns_active_line_for_open_position() -> None:
    service = StopLossOverlayService()
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

    overlay = service.build(position)

    assert overlay == StopLossOverlay(
        active=True,
        market="KRW-XRP",
        stop_loss_price=805.24,
        label="STOP LOSS",
    )


def test_stop_loss_overlay_service_returns_inactive_when_position_closed() -> None:
    service = StopLossOverlayService()

    overlay = service.build(None)

    assert overlay == StopLossOverlay(
        active=False,
        market=None,
        stop_loss_price=None,
        label=None,
    )

