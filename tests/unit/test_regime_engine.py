from __future__ import annotations

from app.services.regime.engine import RegimeEngine, RegimeScorer, RegimeSnapshot
from app.services.signals.features import FeatureSnapshot


def test_regime_engine_marks_risk_off_and_reduces_size() -> None:
    engine = RegimeEngine()
    features = FeatureSnapshot(
        ret_1s=-0.006,
        ret_5s=-0.014,
        ret_30s=-0.022,
        volume_multiple=1.6,
        traded_value_multiple=1.8,
        spread_bps=21.0,
        orderbook_imbalance=-0.31,
        short_volatility=0.021,
        regime_score=0.18,
        liquidity_score=0.42,
    )

    snapshot = engine.evaluate(
        features,
        recent_loss_streak=2,
        safe_mode=False,
    )

    assert snapshot == RegimeSnapshot(
        label="risk_off",
        score=0.14,
        size_multiplier=0.45,
        entry_allowed=False,
        reason_codes=["NEGATIVE_MOMENTUM", "WIDE_SPREAD", "ORDERBOOK_SELL_PRESSURE"],
    )


def test_regime_engine_marks_risk_on_when_market_quality_is_good() -> None:
    engine = RegimeEngine()
    features = FeatureSnapshot(
        ret_1s=0.003,
        ret_5s=0.011,
        ret_30s=0.024,
        volume_multiple=2.1,
        traded_value_multiple=2.0,
        spread_bps=7.0,
        orderbook_imbalance=0.24,
        short_volatility=0.008,
        regime_score=0.77,
        liquidity_score=0.86,
    )

    snapshot = engine.evaluate(
        features,
        recent_loss_streak=0,
        safe_mode=False,
    )

    assert snapshot == RegimeSnapshot(
        label="risk_on",
        score=0.75,
        size_multiplier=1.1,
        entry_allowed=True,
        reason_codes=["POSITIVE_MOMENTUM", "TIGHT_SPREAD", "ORDERBOOK_BUY_PRESSURE"],
    )


def test_regime_engine_blocks_entry_during_safe_mode() -> None:
    engine = RegimeEngine()
    features = FeatureSnapshot(
        ret_1s=0.004,
        ret_5s=0.013,
        ret_30s=0.021,
        volume_multiple=1.9,
        traded_value_multiple=1.8,
        spread_bps=8.0,
        orderbook_imbalance=0.19,
        short_volatility=0.009,
        regime_score=0.64,
        liquidity_score=0.8,
    )

    snapshot = engine.evaluate(
        features,
        recent_loss_streak=0,
        safe_mode=True,
    )

    assert snapshot.entry_allowed is False
    assert snapshot.size_multiplier == 0.0
    assert "SAFE_MODE_ACTIVE" in snapshot.reason_codes


def test_regime_score_calculation_is_reusable() -> None:
    features = FeatureSnapshot(
        ret_1s=0.003,
        ret_5s=0.011,
        ret_30s=0.024,
        volume_multiple=2.1,
        traded_value_multiple=2.0,
        spread_bps=7.0,
        orderbook_imbalance=0.24,
        short_volatility=0.008,
        regime_score=0.77,
        liquidity_score=0.86,
    )

    scorer = RegimeScorer()
    engine = RegimeEngine(scorer=scorer)

    assert scorer.score(features, recent_loss_streak=0) == 0.75
    assert engine.evaluate(features, recent_loss_streak=0, safe_mode=False).score == 0.75
