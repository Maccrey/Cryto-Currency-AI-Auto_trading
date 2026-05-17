from __future__ import annotations

from app.services.risk.sideways import SidewaysMarketRiskGuard


def test_sideways_guard_blocks_relaxed_weak_entry_when_price_and_value_are_flat() -> None:
    guard = SidewaysMarketRiskGuard()

    decision = guard.check(
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
    guard = SidewaysMarketRiskGuard()

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
