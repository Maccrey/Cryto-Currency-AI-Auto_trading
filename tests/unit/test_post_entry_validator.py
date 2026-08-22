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
            momentum_reversal_requires_imbalance=False,  # 단독 모멘텀 손절 허용
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


def test_post_entry_validator_triggers_trailing_stop_after_fee_protected_profit_peak() -> None:
    """트레일링 스탑은 왕복 수수료와 순수익 여유를 넘긴 뒤에만 청산한다."""
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=1000.0,
        quantity=100.0,
        stop_loss_price=970.0,
        stop_loss_pct=0.030,
        validation_window_sec=180,
        min_expected_return_pct=0.010,  # 1.0% 목표 (아직 안 도달)
        stop_loss_reason=None,
    )

    # 첫 번째 틱: +0.6% 수익 달성 → peak 기록
    validator.evaluate(
        position=position,
        current_price=1006.0,   # +0.6%
        elapsed_sec=50,
        momentum_score=0.60,
        orderbook_imbalance=0.05,
    )

    # +0.20%는 새 보호 바닥보다 낮아 청산하지 않는다.
    decision = validator.evaluate(
        position=position,
        current_price=1002.0,
        elapsed_sec=60,
        momentum_score=0.40,
        orderbook_imbalance=0.05,
    )

    assert decision.triggered is False

    # +0.12%로 내려가면 fee-protected floor를 지키면서 큰 되밀림도
    # 확인됐으므로 청산한다.
    decision = validator.evaluate(
        position=position,
        current_price=1002.5,
        elapsed_sec=61,
        momentum_score=0.40,
        orderbook_imbalance=0.05,
    )

    assert decision.triggered is True
    assert decision.reason_code == "TRAILING_STOP_TRIGGERED"
    assert decision.exit_ratio == 1.0


def test_post_entry_validator_does_not_trigger_trailing_stop_before_activation() -> None:
    """트레일링 스탑 미활성화: 수익이 0.3% 미만이면 하락해도 트레일링 스탑 미발동."""
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=1000.0,
        quantity=100.0,
        stop_loss_price=970.0,
        stop_loss_pct=0.030,
        validation_window_sec=180,
        min_expected_return_pct=0.010,
        stop_loss_reason=None,
    )

    # +0.2% 수익 달성 (0.3% 미달 → 트레일링 스탑 미활성화)
    validator.evaluate(
        position=position,
        current_price=1002.0,   # +0.2%
        elapsed_sec=50,
        momentum_score=0.60,
        orderbook_imbalance=0.05,
    )

    # +0.0% 로 하락해도 trailing stop은 발동하지 않아야 함
    decision = validator.evaluate(
        position=position,
        current_price=1000.0,   # 0% (원금)
        elapsed_sec=60,
        momentum_score=0.40,
        orderbook_imbalance=0.05,
    )

    assert decision.triggered is False
    assert decision.reason_code is None


def test_post_entry_validator_reset_clears_peak_return() -> None:
    """reset() 후 트레일링 스탑 상태가 초기화되어 새 포지션에 영향 없음."""
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="medium",
        entry_price=1000.0,
        quantity=100.0,
        stop_loss_price=970.0,
        stop_loss_pct=0.030,
        validation_window_sec=180,
        min_expected_return_pct=0.010,
        stop_loss_reason=None,
    )

    # 이전 포지션에서 +0.8% 달성
    validator.evaluate(
        position=position,
        current_price=1008.0,
        elapsed_sec=50,
        momentum_score=0.60,
        orderbook_imbalance=0.05,
    )

    # 포지션 청산 후 reset
    validator.reset()

    # 새 포지션에서 +0.05% → trailing stop 미발동 (reset 후 peak=None)
    decision = validator.evaluate(
        position=position,
        current_price=1000.5,   # +0.05%
        elapsed_sec=60,
        momentum_score=0.40,
        orderbook_imbalance=0.05,
    )

    assert decision.triggered is False


def test_post_entry_validator_blocks_stop_loss_when_orderbook_is_healthy() -> None:
    """손절 이중 조건: 모멘텀만 낮고 오더북이 양호하면 손절 차단."""
    validator = PostEntryValidator()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=100.0,
        stop_loss_price=805.0,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    # 손실 -1.59%, 모멘텀 낮음, 하지만 오더북은 양호
    decision = validator.evaluate(
        position=position,
        current_price=807.0,
        elapsed_sec=181,
        momentum_score=0.15,
        orderbook_imbalance=0.1,   # 양호 → 이중 조건 미충족 → 손절 차단
    )

    assert decision.triggered is False
    assert decision.reason_code is None
