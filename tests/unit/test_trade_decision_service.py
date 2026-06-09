from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeEngine
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.sizing.engine import SizingEngine
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService


def test_trade_decision_service_evaluates_full_entry_path() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )

    result = service.evaluate(
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
            safe_mode=False,
            recent_loss_streak=0,
        ),
    )

    assert result.signal.level in {"medium", "strong", "very_strong"}
    assert result.regime.entry_allowed is True
    assert result.sizing.allowed is True
    assert result.sizing.buy_amount > 0


def test_trade_decision_service_blocks_entry_in_safe_mode() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )

    result = service.evaluate(
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
            safe_mode=True,
            recent_loss_streak=0,
        ),
    )

    assert result.regime.entry_allowed is False
    assert result.sizing.allowed is False
    assert result.sizing.blocked_reason == "REGIME_BLOCKED"


def test_trade_decision_service_adjusts_signal_with_external_context_weight() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )
    request = TradeDecisionRequest(
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
        safe_mode=False,
        recent_loss_streak=0,
        external_context_weight=1.25,
    )

    result = service.evaluate(request)

    assert result.signal.score > 0
    assert "EXTERNAL_CONTEXT_BULLISH_BOOST" in result.signal.reason_codes


def test_trade_decision_service_uses_observed_price_card_market_state_for_sizing() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )
    base_request = TradeDecisionRequest(
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
        safe_mode=False,
        recent_loss_streak=0,
    )

    bull = service.evaluate(base_request)
    bear = service.evaluate(
        TradeDecisionRequest(
            **{
                **base_request.__dict__,
                "observed_market_state": "bear",
                "observed_market_state_label": "하락장",
            },
        ),
    )

    assert bull.regime.market_state == "bull"
    assert bear.regime.market_state == "bear"
    assert bear.sizing.buy_ratio < bull.sizing.buy_ratio


def test_trade_decision_service_promotes_supported_bull_weak_signal_to_medium() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )

    result = service.evaluate(
        TradeDecisionRequest(
            prices=[1000.0, 999.9, 1000.2, 1000.1, 1000.4, 1000.3, 1000.6],
            traded_values=[1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0],
            spread_bps=8.0,
            orderbook_imbalance=0.02,
            liquidity_score=0.9,
            regime_score=0.7,
            current_price=1000.6,
            slippage_bps=10.0,
            portfolio=PortfolioState(
                cash_balance=500000.0,
                asset_currency="XRP",
                asset_balance=0.0,
                avg_buy_price=0.0,
            ),
            safe_mode=False,
            recent_loss_streak=0,
            observed_market_state="bull",
            observed_market_state_label="상승장",
        ),
    )

    assert result.signal.level == "medium"
    assert result.signal.score == 0.4
    assert "BULL_MARKET_PARTICIPATION_BOOST" in result.signal.reason_codes
    assert result.sizing.allowed is True


def test_trade_decision_service_allows_confirmed_bear_rebound_participation() -> None:
    service = TradeDecisionService(
        feature_calculator=MarketFeatureCalculator(),
        signal_engine=SignalEngine(),
        regime_engine=RegimeEngine(),
        sizing_engine=SizingEngine(
            min_cash_reserve=100000.0,
            max_spread_bps=15.0,
            max_slippage_bps=20.0,
        ),
    )

    result = service.evaluate(
        TradeDecisionRequest(
            prices=[1000.0, 999.0, 1000.2, 999.4, 1000.4, 999.6, 1000.6],
            traded_values=[1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0],
            spread_bps=8.0,
            orderbook_imbalance=0.01,
            liquidity_score=0.9,
            regime_score=0.7,
            current_price=1000.6,
            slippage_bps=10.0,
            portfolio=PortfolioState(
                cash_balance=500000.0,
                asset_currency="XRP",
                asset_balance=0.0,
                avg_buy_price=0.0,
            ),
            safe_mode=False,
            recent_loss_streak=0,
            observed_market_state="bear",
            observed_market_state_label="하락장",
        ),
    )

    assert result.regime.market_state == "bear"
    assert result.signal.level == "medium"
    assert "BEAR_REBOUND_PARTICIPATION" in result.signal.reason_codes
    assert result.regime.entry_allowed is True
    assert result.sizing.allowed is True
