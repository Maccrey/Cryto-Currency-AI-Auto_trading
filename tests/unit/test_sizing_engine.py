from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.sizing.engine import BuySizingPolicy, SellSizingPolicy, SizingDecision, SizingEngine


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
        sell_ratio=0.0,
        sell_amount=0.0,
        sell_quantity=0.0,
        stop_loss_price=785.6,
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


def test_sizing_engine_blocks_buy_when_current_price_is_invalid() -> None:
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
        current_price=0.0,
        spread_bps=9.0,
        slippage_bps=11.0,
    )

    assert decision.allowed is False
    assert decision.blocked_reason == "INVALID_CURRENT_PRICE"


def test_sizing_engine_blocks_scalping_entry_when_edge_does_not_clear_fees() -> None:
    engine = SizingEngine(
        min_cash_reserve=100000,
        max_spread_bps=15,
        max_slippage_bps=20,
        trading_fee_rate=0.0005,
        min_net_edge_pct=0.0008,
    )
    portfolio = PortfolioState(
        cash_balance=300000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="medium", score=0.45, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="neutral",
            score=0.5,
            size_multiplier=0.8,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=9.0,
        slippage_bps=11.0,
    )

    assert decision.allowed is False
    assert decision.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT"


def test_sizing_engine_caps_buy_amount_by_stop_loss_risk_budget() -> None:
    engine = SizingEngine(
        min_cash_reserve=100000,
        max_spread_bps=15,
        max_slippage_bps=20,
        max_stop_loss_risk_amount=1000,
    )
    portfolio = PortfolioState(
        cash_balance=900000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="strong", score=0.72, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="risk_on",
            score=0.72,
            size_multiplier=1.1,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )

    assert decision.allowed is True
    assert decision.buy_amount == 55555.6
    assert decision.buy_quantity == 69.4445
    assert decision.stop_loss_price == 785.6


def test_buy_and_sell_sizing_policies_are_separate() -> None:
    buy_policy = BuySizingPolicy()
    sell_policy = SellSizingPolicy()

    assert buy_policy.ratio_for("strong") == 0.35
    assert sell_policy.ratio_for("strong") == 0.45


def test_sizing_engine_includes_sell_size_and_stop_loss_price() -> None:
    engine = SizingEngine(min_cash_reserve=100000, max_spread_bps=15, max_slippage_bps=20)
    portfolio = PortfolioState(
        cash_balance=500000.0,
        asset_currency="XRP",
        asset_balance=200.0,
        avg_buy_price=780.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="strong", score=0.72, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="neutral",
            score=0.5,
            size_multiplier=0.8,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )

    assert decision.sell_ratio == 0.45
    assert decision.sell_quantity == 90.0
    assert decision.sell_amount == 72000.0
    assert decision.stop_loss_price == 785.6
