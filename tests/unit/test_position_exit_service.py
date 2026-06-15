from app.services.execution.demo import DemoExecutor
from app.services.learning.service import LearningEvent
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.exit import PositionExitService, RegularSellExecutor, StopLossSellExecutor
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
        self.entry_prices = []
        self.total_asset_values = []

    def notify_fill(self, fill, *, reason_code=None, entry_price=None, total_asset_value=None, **kwargs) -> None:
        self.fills.append(fill)
        self.reason_codes.append(reason_code)
        self.entry_prices.append(entry_price)
        self.total_asset_values.append(total_asset_value)


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
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=0.1,
    )

    assert result["status"] == "ok"
    assert result["trigger"] == {
        "type": "post_entry",
        "reason_code": "STOP_LOSS_MOMENTUM_REVERSAL",
        "exit_ratio": 0.55,
    }
    assert result["execution"]["filled_quantity"] == 55.0
    assert result["position"]["quantity"] == 45.0
    assert store.get() is not None
    assert store.get().quantity == 45.0
    records = lifecycle_ledger.list_records()
    assert len(records) == 1
    assert records[0].event_type == "reduced"


def test_position_exit_service_full_exits_when_partial_would_leave_dust() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=10.0,
            stop_loss_price=780.0,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=0.1,
    )

    assert result["status"] == "ok"
    assert result["trigger"]["exit_ratio"] == 1.0
    assert result["execution"]["filled_quantity"] == 10.0
    assert result["position"] is None
    assert store.get() is None


def test_position_exit_service_blocks_sell_below_upbit_minimum_order_amount() -> None:
    store = CurrentPositionStore()
    learning_service = LearningServiceStub()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=5.0,
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
        learning_service=learning_service,
    )

    result = service.evaluate_and_execute(
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=0.1,
    )

    assert result["status"] == "blocked"
    assert result["trigger"]["blocked_reason"] == "MIN_ORDER_AMOUNT_SELL"
    assert result["execution"] is None
    assert store.get() is not None
    assert learning_service.events[0].event_name == "position_exit_blocked"


def test_position_exit_service_uses_inverse_chart_strength_for_take_profit_sell_ratio() -> None:
    store = CurrentPositionStore()
    learning_service = LearningServiceStub()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="medium",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=810.16,
            stop_loss_pct=0.012,
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
    )

    result = service.evaluate_and_execute(
        current_price=826.0,
        elapsed_sec=60,
        momentum_score=0.6,
        orderbook_imbalance=0.1,
        market_state="bull",
    )

    assert result["status"] == "ok"
    assert result["trigger"]["type"] == "take_profit"
    assert result["trigger"]["reason_code"] == "TAKE_PROFIT_TARGET_HIT"
    assert result["trigger"]["exit_ratio"] == 0.75
    assert result["trigger"]["take_profit_target_pct"] == 0.006
    assert result["trigger"]["estimated_net_return_pct"] == 0.006317
    assert result["execution"]["side"] == "sell"
    assert result["execution"]["is_stop_loss"] is False
    assert result["execution"]["filled_quantity"] == 75.0
    assert result["position"]["quantity"] == 25.0
    assert result["position"]["stop_loss_price"] > 820.0
    assert result["position"]["stop_loss_reason"] == "PROFIT_PROTECTED"
    assert learning_service.events[0].payload["trigger_type"] == "take_profit"


def test_position_exit_service_sells_more_of_weak_signal_take_profit() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="weak",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=795.4,
            stop_loss_pct=0.030,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=826.0,
        elapsed_sec=60,
        momentum_score=0.6,
        orderbook_imbalance=0.1,
        market_state="bull",
    )

    assert result["status"] == "ok"
    assert result["trigger"]["type"] == "take_profit"
    assert result["trigger"]["exit_ratio"] == 1.0
    assert result["execution"]["filled_quantity"] == 100.0
    assert result["position"] is None


def test_position_exit_service_sells_more_when_take_profit_chart_strength_is_weak() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="medium",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=810.16,
            stop_loss_pct=0.012,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=826.0,
        elapsed_sec=60,
        momentum_score=-0.5,
        orderbook_imbalance=-0.4,
        market_state="bear",
    )

    assert result["trigger"]["exit_ratio"] == 1.0
    assert result["execution"]["filled_quantity"] == 100.0
    assert result["position"] is None


def test_position_exit_service_full_exits_weak_post_entry_stop() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="weak",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=795.4,
            stop_loss_pct=0.030,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=0.1,
    )

    assert result["status"] == "ok"
    assert result["trigger"]["reason_code"] == "STOP_LOSS_MOMENTUM_REVERSAL"
    assert result["trigger"]["exit_ratio"] == 1.0
    assert result["execution"]["filled_quantity"] == 100.0
    assert result["position"] is None


def test_position_exit_service_waits_for_higher_take_profit_when_market_strength_is_high() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="medium",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=810.16,
            stop_loss_pct=0.012,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=824.0,
        elapsed_sec=60,
        momentum_score=0.6,
        orderbook_imbalance=0.1,
        market_state="bull",
    )

    assert result["status"] == "ok"
    assert result["trigger"] is None
    assert result["execution"] is None
    assert store.get() is not None


def test_position_exit_service_blocks_take_profit_until_fees_are_covered() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="medium",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=810.16,
            stop_loss_pct=0.012,
            validation_window_sec=180,
            min_expected_return_pct=0.001,
            stop_loss_reason=None,
        ),
    )
    service = _build_service(store)

    result = service.evaluate_and_execute(
        current_price=821.7,
        elapsed_sec=60,
        momentum_score=-0.5,
        orderbook_imbalance=-0.4,
        market_state="bear",
    )

    assert result["status"] == "ok"
    assert result["trigger"] is None
    assert result["execution"] is None
    assert store.get() is not None


def test_position_exit_service_sells_at_profitable_box_range_high() -> None:
    store = CurrentPositionStore()
    learning_service = LearningServiceStub()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="weak",
            entry_price=1001.0,
            quantity=100.0,
            stop_loss_price=970.97,
            stop_loss_pct=0.030,
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
    )

    result = service.evaluate_and_execute(
        current_price=1032.0,
        elapsed_sec=60,
        momentum_score=0.1,
        orderbook_imbalance=0.1,
        market_state="box",
        box_range_low=1000.0,
        box_range_high=1040.0,
    )

    assert result["status"] == "ok"
    assert result["trigger"] == {
        "type": "box_range_take_profit",
        "reason_code": "BOX_RANGE_HIGH_TAKE_PROFIT",
        "exit_ratio": 1.0,
        "box_range_low": 1000.0,
        "box_range_high": 1040.0,
    }
    assert result["execution"]["side"] == "sell"
    assert result["execution"]["is_stop_loss"] is False
    assert result["execution"]["filled_quantity"] == 100.0
    assert store.get() is None
    assert learning_service.events[0].payload["trigger_type"] == "box_range_take_profit"


def test_regular_and_stop_loss_sell_executors_set_stop_loss_flag() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.intents = []

        def execute(self, intent):
            self.intents.append(intent)
            return intent

    executor = RecordingExecutor()
    regular = RegularSellExecutor(executor=executor)
    stop_loss = StopLossSellExecutor(executor=executor)

    regular.execute(market="KRW-XRP", price=830.0, quantity=10.0)
    stop_loss.execute(market="KRW-XRP", price=805.0, quantity=10.0)

    assert executor.intents[0].is_stop_loss is False
    assert executor.intents[1].is_stop_loss is True
