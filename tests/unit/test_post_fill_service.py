from app.services.execution.demo import DemoExecutor
from app.services.learning.service import LearningEvent
from app.services.portfolio.sync import PortfolioState
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.regime.engine import RegimeEngine
from app.services.risk.stop_loss import StopLossInjector
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.sizing.engine import SizingEngine
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in demo execution")


class TelegramNotifierStub:
    def __init__(self) -> None:
        self.fills = []
        self.total_asset_values = []

    def notify_fill(self, fill, *, total_asset_value=None) -> None:
        self.fills.append(fill)
        self.total_asset_values.append(total_asset_value)


class LearningServiceStub:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)


def _build_execution_result(safe_mode: bool = False):
    decision_service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )
    execution_service = TradeExecutionService(
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        market="KRW-XRP",
    )
    decision = decision_service.evaluate(
        TradeDecisionRequest(
            prices=[800.0, 806.0, 813.0, 820.0],
            traded_values=[800000.0, 850000.0, 1200000.0, 2100000.0],
            spread_bps=8.0,
            orderbook_imbalance=0.24,
            liquidity_score=0.9,
            regime_score=0.78,
            current_price=820.0,
            slippage_bps=10.0,
            portfolio=PortfolioState(
                cash_balance=500000.0,
                asset_currency="XRP",
                asset_balance=0.0,
                avg_buy_price=0.0,
            ),
            safe_mode=safe_mode,
            recent_loss_streak=0,
        ),
    )
    return execution_service.execute(decision)


def test_post_fill_service_injects_position_for_buy_fill() -> None:
    store = CurrentPositionStore()
    notifier = TelegramNotifierStub()
    lifecycle_ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: "2026-04-19T21:20:00+09:00",
    )
    learning_service = LearningServiceStub()
    service = PostFillService(
        stop_loss_injector=StopLossInjector(
            stop_loss_by_signal={
                "weak": 0.008,
                "medium": 0.012,
                "strong": 0.018,
                "very_strong": 0.022,
            },
            validation_window_sec=180,
            min_expected_return_pct=0.004,
        ),
        position_store=store,
        telegram_notifier=notifier,
        position_lifecycle_ledger=lifecycle_ledger,
        learning_service=learning_service,
    )

    result = service.process(_build_execution_result())

    assert result.position is not None
    assert result.position.market == "KRW-XRP"
    assert result.position.stop_loss_price > 0
    assert store.get() == result.position
    assert len(notifier.fills) == 1
    assert notifier.fills[0].side == "buy"
    assert notifier.fills[0].is_stop_loss is False
    records = lifecycle_ledger.list_records()
    assert len(records) == 1
    assert records[0].event_type == "opened"
    assert [event.event_name for event in learning_service.events] == ["position_opened"]


def test_post_fill_service_merges_additional_buy_into_current_position() -> None:
    store = CurrentPositionStore()
    store.save(
        StopLossInjector(
            stop_loss_by_signal={
                "weak": 0.008,
                "medium": 0.012,
                "strong": 0.018,
                "very_strong": 0.022,
            },
            validation_window_sec=180,
            min_expected_return_pct=0.004,
        ).inject(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=10.0,
        ),
    )
    lifecycle_ledger = PositionLifecycleLedger()
    service = PostFillService(
        stop_loss_injector=StopLossInjector(
            stop_loss_by_signal={
                "weak": 0.008,
                "medium": 0.012,
                "strong": 0.018,
                "very_strong": 0.022,
            },
            validation_window_sec=180,
            min_expected_return_pct=0.004,
        ),
        position_store=store,
        position_lifecycle_ledger=lifecycle_ledger,
    )

    result = service.process(_build_execution_result())

    assert result.position is not None
    assert result.position.quantity > 10.0
    assert result.position.entry_price > 820.0
    assert store.get() == result.position
    assert lifecycle_ledger.list_records()[0].event_type == "increased"


def test_post_fill_service_skips_position_when_execution_blocked() -> None:
    notifier = TelegramNotifierStub()
    service = PostFillService(
        stop_loss_injector=StopLossInjector(
            stop_loss_by_signal={
                "weak": 0.008,
                "medium": 0.012,
                "strong": 0.018,
                "very_strong": 0.022,
            },
            validation_window_sec=180,
            min_expected_return_pct=0.004,
        ),
        telegram_notifier=notifier,
    )

    result = service.process(_build_execution_result(safe_mode=True))

    assert result.position is None
    assert notifier.fills == []
