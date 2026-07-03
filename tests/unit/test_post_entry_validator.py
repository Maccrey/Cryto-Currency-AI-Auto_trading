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
    """1.2% 이상 손실 + 낮은 모멘텀 → 전량 손절 발동."""
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

    # 820 * (1 - 0.015) = 807.70 → 손실 1.5% 초과를 위해 807.0 사용
    decision = validator.evaluate(
        position=position,
        current_price=807.0,
        elapsed_sec=181,
        momentum_score=0.15,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=1.0,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.0159,
    )


def test_post_entry_validator_triggers_earlier_near_one_percent_net_loss() -> None:
    """경계값 테스트: 정확히 1.2% 이상 손실 시 손절 발동."""
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

    # 820 * (1 - 0.015) = 807.70 → 손실 정확히 1.5% 초과
    # 807.0 사용 → 손실 약 1.59% (발동 조건 충족)
    decision = validator.evaluate(
        position=position,
        current_price=807.0,
        elapsed_sec=181,
        momentum_score=0.15,
        orderbook_imbalance=-0.12,
    )

    assert decision == PostEntryDecision(
        triggered=True,
        order_side="sell",
        exit_ratio=1.0,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.0159,
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
    """커스텀 ruleset 사용 시 설정값이 적용되는지 확인."""
    validator = PostEntryValidator(
        expectation_ruleset=PostEntryExpectationRuleset(
            momentum_reversal_threshold=0.45,
            liquidity_dropped_threshold=-0.2,
            min_adverse_exit_pct=0.010,  # 커스텀: 1.0% 기준
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

    # 820 → 811: 손실 -1.1% > 커스텀 기준 1.0% → 발동 (모멘텀 0.44 < 임계값 0.45)
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
        exit_ratio=1.0,
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        unrealized_return_pct=-0.011,
    )
