from __future__ import annotations

from app.services.risk.reentry import (
    FixedCooldownReentryPolicy,
    ReentryBlockDecision,
    ReentryBlocker,
)


def test_reentry_blocker_rejects_entry_within_block_window() -> None:
    blocker = ReentryBlocker(block_seconds=180)

    blocker.record_stop_loss(market="KRW-XRP", triggered_at=1_000)
    decision = blocker.check(market="KRW-XRP", now=1_120)

    assert decision == ReentryBlockDecision(
        allowed=False,
        remaining_seconds=60,
        reason_code="REENTRY_BLOCK_ACTIVE",
    )


def test_reentry_blocker_allows_entry_after_block_window_expires() -> None:
    blocker = ReentryBlocker(block_seconds=180)

    blocker.record_stop_loss(market="KRW-XRP", triggered_at=1_000)
    decision = blocker.check(market="KRW-XRP", now=1_181)

    assert decision == ReentryBlockDecision(
        allowed=True,
        remaining_seconds=0,
        reason_code=None,
    )


def test_reentry_blocker_isolated_per_market() -> None:
    blocker = ReentryBlocker(block_seconds=180)

    blocker.record_stop_loss(market="KRW-BTC", triggered_at=1_000)
    decision = blocker.check(market="KRW-XRP", now=1_050)

    assert decision == ReentryBlockDecision(
        allowed=True,
        remaining_seconds=0,
        reason_code=None,
    )


def test_reentry_blocker_accepts_custom_cooldown_policy() -> None:
    blocker = ReentryBlocker(
        cooldown_policy=FixedCooldownReentryPolicy(block_seconds=300),
    )

    blocker.record_stop_loss(market="KRW-XRP", triggered_at=1_000)
    decision = blocker.check(market="KRW-XRP", now=1_120)

    assert decision == ReentryBlockDecision(
        allowed=False,
        remaining_seconds=180,
        reason_code="REENTRY_BLOCK_ACTIVE",
    )


def test_reentry_blocker_rejects_after_any_sell_with_reason_context() -> None:
    blocker = ReentryBlocker(block_seconds=180)

    blocker.record_exit(
        market="KRW-XRP",
        side="sell",
        reason_code="TAKE_PROFIT_TARGET_HIT",
        triggered_at=1_000,
        price=800.0,
    )
    decision = blocker.check(market="KRW-XRP", now=1_030, current_price=801.0)

    assert decision.allowed is False
    assert decision.reason_code == "REENTRY_BLOCK_AFTER_SELL"
    assert decision.last_exit_reason_code == "TAKE_PROFIT_TARGET_HIT"
    assert decision.last_exit_price == 800.0
