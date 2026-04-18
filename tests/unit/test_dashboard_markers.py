from __future__ import annotations

from app.services.dashboard.markers import ChartMarker, DashboardMarkerService, TradeEvent


def test_dashboard_marker_service_builds_buy_marker_with_blue_color() -> None:
    service = DashboardMarkerService()

    marker = service.build_marker(
        TradeEvent(
            event_type="buy",
            market="KRW-XRP",
            price=820.0,
            quantity=120.5,
            timestamp="2026-04-18T12:30:00+09:00",
            reason="MOMENTUM_BREAKOUT",
            stop_loss_price=805.24,
        ),
    )

    assert marker == ChartMarker(
        event_type="buy",
        market="KRW-XRP",
        color="blue",
        price=820.0,
        timestamp="2026-04-18T12:30:00+09:00",
        tooltip={
            "market": "KRW-XRP",
            "price": 820.0,
            "quantity": 120.5,
            "reason": "MOMENTUM_BREAKOUT",
            "stop_loss_price": 805.24,
        },
    )


def test_dashboard_marker_service_builds_sell_marker_with_red_color() -> None:
    service = DashboardMarkerService()

    marker = service.build_marker(
        TradeEvent(
            event_type="sell",
            market="KRW-XRP",
            price=835.0,
            quantity=100.0,
            timestamp="2026-04-18T12:45:00+09:00",
            reason="TAKE_PROFIT",
            stop_loss_price=None,
        ),
    )

    assert marker.color == "red"
    assert marker.tooltip["reason"] == "TAKE_PROFIT"


def test_dashboard_marker_service_builds_stop_loss_marker_with_yellow_color() -> None:
    service = DashboardMarkerService()

    marker = service.build_marker(
        TradeEvent(
            event_type="stop_loss",
            market="KRW-XRP",
            price=805.0,
            quantity=190.5,
            timestamp="2026-04-18T13:00:00+09:00",
            reason="STOP_LOSS_PRICE_HIT",
            stop_loss_price=805.24,
        ),
    )

    assert marker.color == "yellow"
    assert marker.tooltip["stop_loss_price"] == 805.24

