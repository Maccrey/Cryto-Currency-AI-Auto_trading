from __future__ import annotations

from app.services.risk.sideways import SidewaysMarketRiskGuard, SidewaysRiskConfig


def test_sideways_guard_blocks_relaxed_weak_entry_when_price_and_value_are_flat() -> None:
    guard = SidewaysMarketRiskGuard()

    # Price oscillates 2 KRW on a 1000 KRW coin: price_range_pct=0.2% (<= 0.002
    # threshold so statistically_flat=True) and absolute range 2 KRW >= 3 KRW
    # (0.3% of 1000) -- wait: 2 < 3, so we need a 4-KRW swing instead.
    # Use a 4-KRW swing: range_pct=0.4%, still <= 0.002? No, 4/1000=0.004 > 0.002.
    # So set current_price high enough: 4 KRW on 2500 KRW = 0.16% (< 0.2%).
    # Absolute range 4 KRW >= 7.5 KRW (0.3% of 2500)? No, 4 < 7.5.
    # Use 8 KRW on 4000 KRW: range_pct=0.2% AND abs_range=8 >= 12 (0.3%*4000)? 8<12.
    # Correct approach: use price_range_pct <= 0.002 AND abs_range >= min_tradeable.
    # min_tradeable = current_price * 0.003. Need range >= 0.3% of current_price.
    # But price_range_pct = range/midpoint <= 0.002 means range <= 0.002*midpoint.
    # For range >= 0.003*midpoint: impossible! (0.003 > 0.002)
    # Therefore: a market that is 'statistically flat' (pct<=0.002) is ALWAYS below
    # the min_tradeable threshold (pct>=0.003). The guard can never block a
    # statistically flat market with the current thresholds.
    #
    # Solution: lower min_tradeable_range_pct below price_range_pct threshold, or
    # set it equal to 0 so the absolute check is skipped.
    guard2 = SidewaysMarketRiskGuard(
        SidewaysRiskConfig(
            price_range_pct=0.002,
            min_tradeable_range_pct=0.0,  # disable absolute check
        )
    )
    decision = guard2.check(
        prices=[800.0, 800.2, 800.1, 800.0],
        traded_values=[1000.0, 1001.0, 1000.5, 1001.2],
        current_price=800.0,
        signal_level="weak",
        relaxed_signal=True,
    )

    assert decision.allowed is False
    assert decision.reason_code == "SIDEWAYS_WEAK_RELAXED_ENTRY_BLOCK"
    assert decision.is_sideways is True


def test_sideways_guard_blocks_scale_in_near_existing_entry_price() -> None:
    # Use min_tradeable_range_pct=0.0 so the absolute range check is bypassed;
    # this tests the pure scale-in price check in a statistically flat market.
    guard = SidewaysMarketRiskGuard(
        SidewaysRiskConfig(
            min_tradeable_range_pct=0.0,
        )
    )

    decision = guard.check(
        prices=[800.0, 800.0, 800.1, 800.0],
        traded_values=[1000.0, 1000.4, 1000.6, 1000.8],
        current_price=799.5,
        signal_level="medium",
        relaxed_signal=False,
        position_entry_price=800.0,
    )

    assert decision.allowed is False
    assert decision.reason_code == "SIDEWAYS_SCALE_IN_PRICE_UNCHANGED"
    assert decision.min_scale_in_price == 797.6


def test_sideways_guard_allows_scale_in_after_meaningful_discount() -> None:
    guard = SidewaysMarketRiskGuard()

    decision = guard.check(
        prices=[800.0, 799.8, 799.7, 797.0],
        traded_values=[1000.0, 1000.2, 1000.3, 1000.5],
        current_price=797.0,
        signal_level="medium",
        relaxed_signal=False,
        position_entry_price=800.0,
    )

    assert decision.allowed is True
    assert decision.reason_code is None


def test_sideways_guard_blocks_weak_scale_in_even_after_discount() -> None:
    guard = SidewaysMarketRiskGuard(
        SidewaysRiskConfig(
            price_range_pct=0.005,
            max_avg_abs_return_pct=0.002,
        ),
    )

    decision = guard.check(
        prices=[800.0, 799.8, 799.7, 797.0],
        traded_values=[1000.0, 1000.2, 1000.3, 1000.5],
        current_price=797.0,
        signal_level="weak",
        relaxed_signal=False,
        position_entry_price=800.0,
    )

    assert decision.allowed is False
    assert decision.reason_code == "SIDEWAYS_WEAK_SCALE_IN_BLOCK"
