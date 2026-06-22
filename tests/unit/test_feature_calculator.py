from __future__ import annotations

from app.services.signals.features import MarketFeatureCalculator


def test_feature_calculator_computes_market_features() -> None:
    calculator = MarketFeatureCalculator()

    snapshot = calculator.calculate(
        prices=[800.0, 804.0, 809.0, 815.0],
        traded_values=[10_000_000.0, 12_000_000.0, 21_000_000.0, 30_000_000.0],
        spread_bps=9.5,
        orderbook_imbalance=0.27,
        liquidity_score=0.82,
        regime_score=0.55,
    )

    assert round(snapshot.ret_1s, 4) == 0.0074
    assert round(snapshot.ret_5s, 4) == 0.0136
    assert round(snapshot.ret_30s, 4) == 0.0186
    assert round(snapshot.volume_multiple, 4) == 1.8182
    assert round(snapshot.traded_value_multiple, 4) == 1.8182
    assert snapshot.spread_bps == 9.5
    assert snapshot.orderbook_imbalance == 0.27
    assert round(snapshot.short_volatility, 4) == 0.0062
    assert snapshot.regime_score == 0.55
    assert snapshot.liquidity_score == 0.82
    assert 0.0 <= snapshot.rsi_14 <= 100.0
    assert snapshot.macd_histogram >= 0.0
    assert 0.0 <= snapshot.bollinger_position <= 1.0
    assert snapshot.ma_trend >= 0.0
    assert 0.0 <= snapshot.stochastic_k <= 100.0
    assert 0.0 <= snapshot.price_position_20 <= 1.0
    assert snapshot.drawdown_from_high_20 <= 0.0
    assert snapshot.rebound_from_low_20 >= 0.0
    assert -1.0 <= snapshot.trend_efficiency_20 <= 1.0


def test_feature_calculator_separates_short_and_long_momentum_windows() -> None:
    snapshot = MarketFeatureCalculator().calculate(
        prices=[100.0, 110.0, 109.0, 108.0],
        traded_values=[100.0, 100.0, 100.0, 100.0],
        spread_bps=5.0,
        orderbook_imbalance=0.0,
        liquidity_score=1.0,
        regime_score=0.5,
    )

    assert snapshot.ret_5s < 0.0
    assert snapshot.ret_30s > 0.0
