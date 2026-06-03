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
        buy_ratio=0.462,
        buy_amount=184800.0,
        buy_quantity=231.0,
        sell_ratio=0.0,
        sell_amount=0.0,
        sell_quantity=0.0,
        stop_loss_price=776.0,
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


def test_sizing_engine_caps_buy_amount_so_fee_never_exceeds_investable_cash() -> None:
    engine = SizingEngine(
        min_cash_reserve=100000,
        max_spread_bps=15,
        max_slippage_bps=20,
        trading_fee_rate=0.0005,
    )
    portfolio = PortfolioState(
        cash_balance=254000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )

    decision = engine.size_entry(
        portfolio,
        SignalDecision(level="very_strong", score=0.9, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="risk_on",
            score=0.8,
            size_multiplier=1.5,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=9.0,
        slippage_bps=11.0,
    )

    assert decision.allowed is True
    assert decision.buy_amount * 1.0005 <= 154000.0


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


def test_sizing_engine_allows_medium_scalping_entry_with_relaxed_edge_buffer() -> None:
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

    assert decision.allowed is True
    assert decision.buy_amount == 34200.0
    assert decision.buy_quantity == 42.75
    assert decision.stop_loss_price == 776.0


def test_sizing_engine_blocks_weak_scalping_entry_when_edge_does_not_clear_fees() -> None:
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
        SignalDecision(level="weak", score=0.12, blocked=False, reason_codes=[]),
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


def test_sizing_engine_can_relax_fee_edge_for_demo_no_trade_recovery() -> None:
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
        SignalDecision(level="weak", score=0.18, blocked=False, reason_codes=[]),
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
        relax_fee_edge=True,
    )

    assert decision.allowed is True
    assert decision.buy_amount == 20000.0
    assert decision.buy_quantity == 25.0


def test_sizing_engine_blocks_buy_below_upbit_minimum_order_amount() -> None:
    engine = SizingEngine(
        min_cash_reserve=100000,
        max_spread_bps=15,
        max_slippage_bps=20,
        min_order_amount_krw=5000,
    )
    portfolio = PortfolioState(
        cash_balance=106000.0,
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
            size_multiplier=1.0,
            entry_allowed=True,
            reason_codes=[],
        ),
        current_price=800.0,
        spread_bps=9.0,
        slippage_bps=11.0,
    )

    assert decision.allowed is False
    assert decision.blocked_reason == "MIN_ORDER_AMOUNT"


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
    assert decision.buy_amount == 25454.5
    assert decision.buy_quantity == 31.8181
    assert decision.stop_loss_price == 776.0


def test_sizing_engine_risk_cap_scales_with_signal_strength() -> None:
    engine = SizingEngine(
        min_cash_reserve=100000,
        max_spread_bps=15,
        max_slippage_bps=20,
        max_stop_loss_risk_amount=37500,
    )
    portfolio = PortfolioState(
        cash_balance=10_000_000.0,
        asset_currency="XRP",
        asset_balance=0.0,
        avg_buy_price=0.0,
    )
    regime = RegimeSnapshot(
        label="risk_on",
        score=0.72,
        size_multiplier=1.4,
        entry_allowed=True,
        reason_codes=[],
    )

    medium = engine.size_entry(
        portfolio,
        SignalDecision(level="medium", score=0.45, blocked=False, reason_codes=[]),
        regime,
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )
    very_strong = engine.size_entry(
        portfolio,
        SignalDecision(level="very_strong", score=0.9, blocked=False, reason_codes=[]),
        regime,
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )

    assert medium.allowed is True
    assert very_strong.allowed is True
    assert medium.buy_amount < very_strong.buy_amount
    assert very_strong.buy_amount == 1_250_000.0


def test_buy_and_sell_sizing_policies_are_separate() -> None:
    buy_policy = BuySizingPolicy()
    sell_policy = SellSizingPolicy()

    assert buy_policy.ratio_for("strong") == 0.35
    assert sell_policy.ratio_for("strong") == 0.45


def test_sizing_policies_scale_from_chart_strength_score() -> None:
    buy_policy = BuySizingPolicy()
    sell_policy = SellSizingPolicy()
    weak_chart = SignalDecision(level="weak", score=0.2, blocked=False, reason_codes=[])
    strong_chart = SignalDecision(level="strong", score=0.75, blocked=False, reason_codes=[])

    assert buy_policy.dynamic_ratio_for(strong_chart) > buy_policy.dynamic_ratio_for(weak_chart)
    assert sell_policy.dynamic_ratio_for(strong_chart) < sell_policy.dynamic_ratio_for(weak_chart)


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

    assert decision.sell_ratio == 0.232
    assert decision.sell_quantity == 46.4
    assert decision.sell_amount == 37120.0
    assert decision.stop_loss_price == 776.0


def test_sizing_engine_adjusts_buy_and_sell_ratios_by_market_state() -> None:
    engine = SizingEngine(min_cash_reserve=100000, max_spread_bps=15, max_slippage_bps=20)
    portfolio = PortfolioState(
        cash_balance=500000.0,
        asset_currency="XRP",
        asset_balance=200.0,
        avg_buy_price=780.0,
    )

    bull = engine.size_entry(
        portfolio,
        SignalDecision(level="strong", score=0.72, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="risk_on",
            score=0.75,
            size_multiplier=1.1,
            entry_allowed=True,
            reason_codes=[],
            market_state="bull",
            market_state_label="상승장",
        ),
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )
    box = engine.size_entry(
        portfolio,
        SignalDecision(level="strong", score=0.72, blocked=False, reason_codes=[]),
        RegimeSnapshot(
            label="neutral",
            score=0.5,
            size_multiplier=0.8,
            entry_allowed=True,
            reason_codes=[],
            market_state="box",
            market_state_label="박스권",
            box_range_low=790.0,
            box_range_high=810.0,
        ),
        current_price=800.0,
        spread_bps=10.0,
        slippage_bps=12.0,
    )

    assert bull.buy_ratio > box.buy_ratio
    assert bull.sell_ratio < box.sell_ratio
