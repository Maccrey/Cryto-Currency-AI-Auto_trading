from app.services.execution.demo import DemoExecutor
from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeEngine
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.sizing.engine import SizingEngine
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService
from app.services.trading.execution import TradeExecutionService


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in demo execution")


def _build_decision(safe_mode: bool = False):
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
    return decision_service.evaluate(
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


def test_trade_execution_service_executes_demo_fill_when_allowed() -> None:
    service = TradeExecutionService(
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        market="KRW-XRP",
    )

    result = service.execute(_build_decision())

    assert result.status == "filled"
    assert result.blocked_reason is None
    assert result.execution is not None
    assert result.execution.mode == "demo"
    assert result.execution.is_virtual is True


def test_trade_execution_service_returns_blocked_without_execution() -> None:
    service = TradeExecutionService(
        executor=DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway()),
        market="KRW-XRP",
    )

    result = service.execute(_build_decision(safe_mode=True))

    assert result.status == "blocked"
    assert result.blocked_reason == "REGIME_BLOCKED"
    assert result.execution is None
