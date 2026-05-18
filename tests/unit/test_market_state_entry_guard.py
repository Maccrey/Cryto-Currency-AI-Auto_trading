from app.services.trading.market_state import MarketStateEntryGuard


def test_market_state_entry_guard_blocks_weak_bear_entries() -> None:
    guard = MarketStateEntryGuard()

    decision = guard.evaluate(
        market_state="bear",
        signal_level="weak",
        signal_score=0.28,
    )

    assert decision.allowed is False
    assert decision.reason_code == "MARKET_STATE_BEAR_ENTRY_BLOCK"
    assert decision.transition_boost is False


def test_market_state_entry_guard_boosts_confirmed_bear_to_bull_reversal() -> None:
    guard = MarketStateEntryGuard(confirmation_ticks=2)
    guard.evaluate(market_state="bear", signal_level="weak", signal_score=0.2)
    first_bull = guard.evaluate(market_state="bull", signal_level="weak", signal_score=0.24)
    second_bull = guard.evaluate(market_state="bull", signal_level="weak", signal_score=0.24)

    assert first_bull.transition_boost is False
    assert second_bull.allowed is True
    assert second_bull.transition_boost is True
    assert second_bull.transition == "bear->bull"
    assert second_bull.current_state_count == 2
