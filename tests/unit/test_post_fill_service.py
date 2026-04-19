from app.services.execution.demo import DemoExecutor
from app.services.portfolio.sync import PortfolioState
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
    )

    result = service.process(_build_execution_result())

    assert result.position is not None
    assert result.position.market == "KRW-XRP"
    assert result.position.stop_loss_price > 0
    assert store.get() == result.position


def test_post_fill_service_skips_position_when_execution_blocked() -> None:
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
    )

    result = service.process(_build_execution_result(safe_mode=True))

    assert result.position is None
