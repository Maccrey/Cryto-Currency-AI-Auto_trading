from __future__ import annotations

from app.services.execution.demo import DemoExecutor, OrderIntent
from app.services.learning.service import LearningEvent
from app.services.portfolio.sync import PortfolioState
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import RecoveryOrchestrator
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import PositionSnapshot, StopLossInjector
from app.services.signals.engine import SignalEngine
from app.services.signals.features import FeatureSnapshot
from app.services.trading.post_fill import PostFillService
from app.services.position.exit import PositionExitService


class StubLearningService:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)

    def record_many(self, events: list[LearningEvent]) -> None:
        self.events.extend(events)


class ForbiddenLiveOrderGateway:
    def place_order(self, *args, **kwargs):
        raise AssertionError("demo executor must not call live order gateway")


class StubRestartStore:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def record(self, event: dict[str, object]) -> None:
        self.events.append(event)


class SuccessfulPortfolioSyncService:
    def sync(self) -> PortfolioState:
        return PortfolioState(
            cash_balance=150000.0,
            asset_currency="XRP",
            asset_balance=120.0,
            avg_buy_price=820.0,
        )


class SuccessfulOpenOrderReconciler:
    def reconcile(self) -> dict[str, object]:
        return {"open_order_count": 0}


def test_signal_engine_records_learning_event() -> None:
    learning_service = StubLearningService()
    engine = SignalEngine(learning_service=learning_service, trading_mode="demo")

    decision = engine.evaluate(
        FeatureSnapshot(
            ret_1s=0.004,
            ret_5s=0.012,
            ret_30s=0.029,
            volume_multiple=2.4,
            traded_value_multiple=2.1,
            spread_bps=8.0,
            orderbook_imbalance=0.32,
            short_volatility=0.011,
            regime_score=0.68,
            liquidity_score=0.74,
        ),
    )

    assert decision.level == "strong"
    assert len(learning_service.events) == 1
    assert learning_service.events[0].event_name == "signal_generated"
    assert learning_service.events[0].payload["level"] == "strong"


def test_demo_executor_records_fill_result_event() -> None:
    learning_service = StubLearningService()
    executor = DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        learning_service=learning_service,
    )

    fill = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=820.0,
            quantity=120.5,
            order_type="limit",
            is_stop_loss=False,
        ),
    )

    assert fill.status == "filled"
    assert len(learning_service.events) == 1
    assert learning_service.events[0].event_name == "fill_result"
    assert learning_service.events[0].payload["filled_price"] == 820.0


def test_recovery_orchestrator_records_restart_and_recovery_events() -> None:
    learning_service = StubLearningService()
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=StubRestartStore(),
        learning_service=learning_service,
    )

    state = orchestrator.boot()

    assert state.trading_ready is True
    assert [event.event_name for event in learning_service.events] == [
        "restart_detected",
        "recovery_completed",
    ]


def test_post_fill_service_records_position_opened_learning_event() -> None:
    learning_service = StubLearningService()
    store = CurrentPositionStore()
    lifecycle_ledger = PositionLifecycleLedger()
    executor = DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        learning_service=learning_service,
    )
    fill = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=820.0,
            quantity=120.5,
            order_type="limit",
            is_stop_loss=False,
        ),
    )
    post_fill_service = PostFillService(
        stop_loss_injector=StopLossInjector(
            stop_loss_by_signal={"strong": 0.018},
            validation_window_sec=180,
            min_expected_return_pct=0.004,
        ),
        position_store=store,
        position_lifecycle_ledger=lifecycle_ledger,
        learning_service=learning_service,
    )

    class Signal:
        level = "strong"

    class Decision:
        signal = Signal()

    class ExecutionResult:
        status = "filled"
        execution = fill
        decision = Decision()

    post_fill_service.process(ExecutionResult())

    assert [event.event_name for event in learning_service.events][-1] == "position_opened"


def test_position_exit_service_records_lifecycle_learning_event() -> None:
    learning_service = StubLearningService()
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=100.0,
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
    )

    service.evaluate_and_execute(
        current_price=805.0,
        elapsed_sec=181,
        momentum_score=0.41,
        orderbook_imbalance=-0.12,
    )

    assert [event.event_name for event in learning_service.events] == [
        "position_exit_completed",
        "position_lifecycle_updated",
    ]
