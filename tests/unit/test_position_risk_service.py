from app.services.position.risk import PositionRiskService
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import PositionSnapshot


def test_position_risk_service_returns_empty_without_position() -> None:
    service = PositionRiskService(
        position_store=CurrentPositionStore(),
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
    )

    result = service.evaluate(
        current_price=800.0,
        elapsed_sec=60,
        momentum_score=0.5,
        orderbook_imbalance=0.1,
    )

    assert result == {
        "status": "empty",
        "position": None,
        "hard_stop": None,
        "post_entry": None,
    }


def test_position_risk_service_evaluates_hard_stop_and_post_entry() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=190.5,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = PositionRiskService(
        position_store=store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
    )

    result = service.evaluate(
        current_price=805.0,
        elapsed_sec=181,
        momentum_score=0.41,
        orderbook_imbalance=-0.12,
    )

    assert result["status"] == "ok"
    assert result["hard_stop"]["triggered"] is True
    assert result["hard_stop"]["reason_code"] == "STOP_LOSS_PRICE_HIT"
    assert result["post_entry"]["triggered"] is False
    assert result["post_entry"]["reason_code"] is None
