from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.sizing.engine import SizingDecision, SizingEngine


def test_sizing_engine_computes_buy_amount_for_strong_signal() -> None:
    engine = SizingEngine(min_cash_reserve=100000, max_spread_bps=15, max_slippage_bps=20)
    portfolio = PortfolioState(
        cash_balance=500000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )
    signal = SignalDecision(
        level="strong",
        score=0.72,
        blocked=False,
        reason_codes=["MOMENTUM_BREAKOUT"],
    )
    regime = RegimeSnapshot(
        label="risk_on",
        score=0.75,
        size_multiplier=1.1,
        entry_allowed=True,
        reason_codes=["POSITIVE_MOMENTUM"],
    )

    decision = engine.size_entry(
        portfolio,
        signal,
        regime,
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )

    assert decision == SizingDecision(
        allowed=True,
        order_side="buy",
        buy_ratio=0.385,
        buy_amount=154000.0,
        buy_quantity=192.5,
        blocked_reason=None,
    )


def test_sizing_engine_blocks_buy_below_cash_reserve() -> None:
    engine = SizingEngine(min_cash_reserve=100000, max_spread_bps=15, max_slippage_bps=20)
    portfolio = PortfolioState(
        cash_balance=95000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="strong", score=0.7, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="neutral",
            score=0.45,
            size_multiplier=0.8,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=9.0,
        slippage_bps=11.0,
    )

    assert decision.allowed is False
    assert decision.blocked_reason == "MIN_CASH_RESERVE"


def test_sizing_engine_blocks_buy_when_spread_or_slippage_exceed_limit() -> None:
    engine = SizingEngine(min_cash_reserve=100000, max_spread_bps=15, max_slippage_bps=20)
    portfolio = PortfolioState(
        cash_balance=300000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="medium", score=0.5, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="neutral",
            score=0.48,
            size_multiplier=0.8,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=810.0,
        spread_bps=18.0,
        slippage_bps=25.0,
    )

    assert decision.allowed is False
    assert decision.blocked_reason == "SPREAD_OR_SLIPPAGE_LIMIT"

