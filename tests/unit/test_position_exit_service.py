from app.services.execution.demo import DemoExecutor
from app.services.position.exit import PositionExitService
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import PositionSnapshot


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in demo execution")


def _build_service(store: CurrentPositionStore) -> PositionExitService:
    return PositionExitService(
        position_store=store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
    )


def test_position_exit_service_returns_empty_without_position() -> None:
    service = _build_service(CurrentPositionStore())

    result = service.evaluate_and_execute(
        current_price=800.0,
        elapsed_sec=60,
        momentum_score=0.5,
        orderbook_imbalance=0.1,
    )

    assert result == {
        "status": "empty",
        "position": None,
        "trigger": None,
        "execution": None,
    }


def test_position_exit_service_executes_full_exit_on_hard_stop() -> None:
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
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=805.0,
        elapsed_sec=181,
        momentum_score=0.41,
        orderbook_imbalance=-0.12,
    )

    assert result["status"] == "ok"
    assert result["trigger"] == {
        "type": "hard_stop",
        "reason_code": "STOP_LOSS_PRICE_HIT",
        "exit_ratio": 1.0,
    }
    assert result["execution"]["side"] == "sell"
    assert result["execution"]["is_stop_loss"] is True
    assert result["position"] is None
    assert store.get() is None


def test_position_exit_service_updates_position_after_partial_post_entry_exit() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=780.0,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=830.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=0.1,
    )

    assert result["status"] == "ok"
    assert result["trigger"] == {
        "type": "post_entry",
        "reason_code": "STOP_LOSS_MOMENTUM_REVERSAL",
        "exit_ratio": 0.5,
    }
    assert result["execution"]["filled_quantity"] == 50.0
    assert result["position"]["quantity"] == 50.0
    assert store.get() is not None
    assert store.get().quantity == 50.0
