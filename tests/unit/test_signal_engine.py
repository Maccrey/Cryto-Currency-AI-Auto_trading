from __future__ import annotations

from app.services.signals.engine import SignalDecision, SignalEngine, SignalReasonCodeGenerator
from app.services.signals.features import FeatureSnapshot


def test_signal_engine_generates_strong_signal_for_momentum_breakout() -> None:
    engine = SignalEngine()
    features = FeatureSnapshot(
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
    )

    decision = engine.evaluate(features)

    assert decision == SignalDecision(
        level="strong",
        score=0.72,
        blocked=False,
        reason_codes=["MOMENTUM_BREAKOUT", "VALUE_ACCELERATION", "ORDERBOOK_SUPPORT"],
    )


def test_signal_engine_blocks_signal_in_low_liquidity_zone() -> None:
    engine = SignalEngine()
    features = FeatureSnapshot(
        ret_1s=0.005,
        ret_5s=0.017,
        ret_30s=0.031,
        volume_multiple=2.7,
        traded_value_multiple=2.5,
        spread_bps=7.0,
        orderbook_imbalance=0.28,
        short_volatility=0.013,
        regime_score=0.61,
        liquidity_score=0.18,
    )

    decision = engine.evaluate(features)

    assert decision.blocked is True
    assert decision.level == "weak"
    assert "LOW_LIQUIDITY_BLOCKED" in decision.reason_codes


def test_signal_engine_blocks_micro_momentum_reversal() -> None:
    engine = SignalEngine()
    features = FeatureSnapshot(
        ret_1s=-0.006,
        ret_5s=0.017,
        ret_30s=0.031,
        volume_multiple=2.7,
        traded_value_multiple=2.5,
        spread_bps=7.0,
        orderbook_imbalance=0.28,
        short_volatility=0.013,
        regime_score=0.61,
        liquidity_score=0.74,
    )

    decision = engine.evaluate(features)

    assert decision.blocked is True
    assert decision.level == "weak"
    assert "MICRO_MOMENTUM_REVERSAL_BLOCKED" in decision.reason_codes


def test_signal_engine_blocks_excessive_short_volatility() -> None:
    engine = SignalEngine()
    features = FeatureSnapshot(
        ret_1s=0.005,
        ret_5s=0.017,
        ret_30s=0.031,
        volume_multiple=2.7,
        traded_value_multiple=2.5,
        spread_bps=7.0,
        orderbook_imbalance=0.28,
        short_volatility=0.04,
        regime_score=0.61,
        liquidity_score=0.74,
    )

    decision = engine.evaluate(features)

    assert decision.blocked is True
    assert decision.level == "weak"
    assert "EXCESSIVE_SHORT_VOLATILITY_BLOCKED" in decision.reason_codes


def test_signal_engine_accepts_reason_code_generator() -> None:
    engine = SignalEngine(reason_code_generator=SignalReasonCodeGenerator())
    features = FeatureSnapshot(
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
    )

    decision = engine.evaluate(features)

    assert decision.reason_codes == [
        "MOMENTUM_BREAKOUT",
        "VALUE_ACCELERATION",
        "ORDERBOOK_SUPPORT",
    ]
