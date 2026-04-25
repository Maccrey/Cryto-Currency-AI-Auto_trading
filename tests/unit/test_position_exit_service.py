from app.services.execution.demo import DemoExecutor
from app.services.learning.service import LearningEvent
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.exit import PositionExitService
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import PositionSnapshot


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in demo execution")


class LearningServiceStub:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)


class TelegramNotifierStub:
    def __init__(self) -> None:
        self.fills = []
        self.reason_codes = []

    def notify_fill(self, fill, *, reason_code=None) -> None:
        self.fills.append(fill)
        self.reason_codes.append(reason_code)


def _build_service(store: CurrentPositionStore) -> PositionExitService:
    return PositionExitService(
        position_store=store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        trading_mode="demo",
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
    learning_service = LearningServiceStub()
    telegram_notifier = TelegramNotifierStub()
    lifecycle_ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: "2026-04-19T21:30:00+09:00",
    )
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
    service = PositionExitService(
        position_store=store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        trading_mode="demo",
        learning_service=learning_service,
        telegram_notifier=telegram_notifier,
        position_lifecycle_ledger=lifecycle_ledger,
    )

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
    assert [event.event_name for event in learning_service.events] == [
        "position_exit_completed",
        "position_lifecycle_updated",
    ]
    assert learning_service.events[0].payload["trigger_type"] == "hard_stop"
    assert learning_service.events[1].payload["event_type"] == "closed"
    assert len(telegram_notifier.fills) == 1
    assert telegram_notifier.fills[0].is_stop_loss is True
    assert telegram_notifier.reason_codes == ["STOP_LOSS_PRICE_HIT"]
    records = lifecycle_ledger.list_records()
    assert len(records) == 1
    assert records[0].event_type == "closed"
    assert records[0].reason_code == "STOP_LOSS_PRICE_HIT"


def test_position_exit_service_updates_position_after_partial_post_entry_exit() -> None:
    store = CurrentPositionStore()
    lifecycle_ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: "2026-04-19T21:31:00+09:00",
    )
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
    service = PositionExitService(
        position_store=store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        trading_mode="demo",
        position_lifecycle_ledger=lifecycle_ledger,
    )

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
    records = lifecycle_ledger.list_records()
    assert len(records) == 1
    assert records[0].event_type == "reduced"
