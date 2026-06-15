from __future__ import annotations

from app.services.risk.post_entry import (
    PostEntryDecision,
    PostEntryExpectationRuleset,
    PostEntryValidator,
)
from app.services.risk.stop_loss import PositionSnapshot


def test_post_entry_validator_holds_near_breakeven_after_window() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=821.0,
        elapsed_sec=181,
        momentum_score=0.41,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=False,
        order_side="sell",
        exit_ratio=0.0,
        reason_code=None,
        unrealized_return_pct=0.0012,
    )


def test_post_entry_validator_holds_small_loss_after_validation_window() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=818.0,
        elapsed_sec=181,
        momentum_score=0.41,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=False,
        order_side="sell",
        exit_ratio=0.0,
        reason_code=None,
        unrealized_return_pct=-0.0024,
    )


def test_post_entry_validator_reduces_after_confirmed_adverse_momentum() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=0.5,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.011,
    )


def test_post_entry_validator_triggers_earlier_near_one_percent_net_loss() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=813.4,
        elapsed_sec=181,
        momentum_score=0.2,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=0.5,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.008,
    )


def test_post_entry_validator_does_not_trigger_before_validation_window() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=810.0,
        quantity=100.0,
        stop_loss_price=800.28,
        stop_loss_pct=0.012,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=810.5,
        elapsed_sec=60,
        momentum_score=0.55,
        orderbook_imbalance=0.08,
    )

    assert decision == PostEntryDecision(
        triggered=False,
        order_side="sell",
        exit_ratio=0.0,
        reason_code=None,
        unrealized_return_pct=0.0006,
    )


def test_post_entry_validator_takes_profit_when_target_is_hit_before_validation_window() -> None:
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=810.0,
        quantity=100.0,
        stop_loss_price=800.28,
        stop_loss_pct=0.012,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=814.0,
        elapsed_sec=60,
        momentum_score=0.55,
        orderbook_imbalance=0.08,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=1.0,
        reason_code="TAKE_PROFIT_TARGET_HIT",
        unrealized_return_pct=0.0049,
    )


def test_post_entry_validator_accepts_custom_expectation_ruleset() -> None:
    validator = PostEntryValidator(
        expectation_ruleset=PostEntryExpectationRuleset(
            momentum_reversal_threshold=0.45,
            liquidity_dropped_threshold=-0.2,
        ),
    )
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.008,
        stop_loss_reason=None,
    )

    decision = validator.evaluate(
        position=position,
        current_price=811.0,
        elapsed_sec=181,
        momentum_score=0.44,
        orderbook_imbalance=0.02,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=0.5,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.011,
    )
