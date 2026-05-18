from app.services.risk.market_shock import MarketShockConfig, MarketShockRiskGuard


def test_market_shock_guard_blocks_entries_after_crash_until_recovery_confirms() -> None:
    guard = MarketShockRiskGuard(
        MarketShockConfig(
            crash_change_pct=-0.015,
            recovery_change_pct=0.003,
            recovery_confirmation_ticks=2,
        ),
    )

    crash = guard.check(prices=[100.0, 99.0, 98.0])
    first_recovery = guard.check(prices=[100.0, 98.0, 100.3])
    confirmed = guard.check(prices=[100.0, 100.3, 100.7])

    assert crash.allowed is False
    assert crash.reason_code == "MARKET_CRASH_OBSERVE_ONLY"
    assert crash.alert_type == "crash"
    assert first_recovery.allowed is False
    assert first_recovery.recovery_count == 1
    assert confirmed.allowed is True
    assert confirmed.shock_state == "recovered"


def test_market_shock_guard_reports_surge_alert_without_blocking() -> None:
    guard = MarketShockRiskGuard(MarketShockConfig(surge_change_pct=0.020))

    decision = guard.check(prices=[100.0, 101.0, 102.5])

    assert decision.allowed is True
    assert decision.shock_state == "surge"
    assert decision.alert_type == "surge"
