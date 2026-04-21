from app.services.dashboard.positions import DashboardPositionsService
from app.services.dashboard.positions_facade import DashboardPositionsFacade
from app.services.position.ledger import PositionLifecycleLedger
from app.services.risk.stop_loss import PositionSnapshot


def test_dashboard_positions_facade_returns_empty_without_records() -> None:
    facade = DashboardPositionsFacade(
        position_lifecycle_ledger=PositionLifecycleLedger(),
        dashboard_positions_service=DashboardPositionsService(),
    )

    payload = facade.build_history_response()

    assert payload == {
        "status": "empty",
        "history": [],
    }


def test_dashboard_positions_facade_returns_recent_history() -> None:
    timestamps = iter(
        [
            "2026-04-19T21:10:00+09:00",
            "2026-04-19T21:10:01+09:00",
        ],
    )
    ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: next(timestamps),
    )
    opened = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=100.0,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )
    reduced = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=50.0,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )
    ledger.record(event_type="opened", position=opened)
    ledger.record(
        event_type="reduced",
        position=reduced,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
    )
    facade = DashboardPositionsFacade(
        position_lifecycle_ledger=ledger,
        dashboard_positions_service=DashboardPositionsService(),
    )

    payload = facade.build_history_response(limit=1)

    assert payload == {
        "status": "ok",
        "history": [
            {
                "event_type": "reduced",
                "severity": "warning",
                "state_message": "포지션이 부분 청산되었습니다.",
                "market": "KRW-XRP",
                "signal_level": "strong",
                "entry_price": 820.0,
                "quantity": 50.0,
                "stop_loss_price": 805.24,
                "reason_code": "STOP_LOSS_MOMENTUM_REVERSAL",
                "recorded_at": "2026-04-19T21:10:01+09:00",
            },
        ],
    }
