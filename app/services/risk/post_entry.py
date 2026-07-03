from __future__ import annotations

from dataclasses import dataclass

from app.services.risk.stop_loss import PositionSnapshot


@dataclass(frozen=True)
class PostEntryDecision:
    triggered: bool
    order_side: str
    exit_ratio: float
    reason_code: str | None
    unrealized_return_pct: float


@dataclass(frozen=True)
class PostEntryExpectationRuleset:
    """Decide how to exit when a new position misses post-entry expectations.

    Tuning notes
    ------------
    * ``min_adverse_exit_pct`` – 포지션 손실이 이 값을 초과해야 손절 발동.
      너무 작으면 단기 휩소에 의해 과민 손절 (loss loop) 발생.
      기본값 0.012 (1.2%) — 수수료 0.05% × 2 + 여유 마진 포함.
    * ``momentum_reversal_threshold`` – 모멘텀 점수가 이 값 미만이어야
      STOP_LOSS_MOMENTUM_REVERSAL 발동. 너무 높으면 정상적인 횡보 구간에서도
      과민 손절. 기본값 0.25.
    * ``liquidity_dropped_threshold`` – 호가 불균형이 이 값보다 낮을 때
      유동성 소멸 손절 발동. 기본값 -0.2.
    """

    momentum_reversal_threshold: float = 0.20   # 강화: 0.35→0.25→0.20 (횡보 오발동 방지)
    liquidity_dropped_threshold: float = -0.2
    min_adverse_exit_pct: float = 0.015          # 강화: 0.8%→1.2%→1.5% (단기 휩소 손절 방지)

    def evaluate(
        self,
        *,
        position: PositionSnapshot,
        unrealized_return_pct: float,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> tuple[float, str] | None:
        if unrealized_return_pct >= position.min_expected_return_pct:
            return (1.0, "TAKE_PROFIT_TARGET_HIT")

        if unrealized_return_pct > -self.min_adverse_exit_pct:
            return None

        if momentum_score < self.momentum_reversal_threshold:
            # 전량 손절(1.0): 부분 손절(0.5) 시 잔량이 계속 손실을 누적하는 문제 해결
            return (1.0, "STOP_LOSS_MOMENTUM_REVERSAL")

        if orderbook_imbalance < self.liquidity_dropped_threshold:
            return (1.0, "STOP_LOSS_LIQUIDITY_DROPPED")

        return None


class PostEntryValidator:
    """Validate whether a freshly opened position is behaving as expected."""

    def __init__(
        self,
        *,
        expectation_ruleset: PostEntryExpectationRuleset | None = None,
    ) -> None:
        self._expectation_ruleset = expectation_ruleset or PostEntryExpectationRuleset()

    def evaluate(
        self,
        *,
        position: PositionSnapshot,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> PostEntryDecision:
        unrealized_return_pct = round((current_price - position.entry_price) / position.entry_price, 4)

        if unrealized_return_pct >= position.min_expected_return_pct:
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=1.0,
                reason_code="TAKE_PROFIT_TARGET_HIT",
                unrealized_return_pct=unrealized_return_pct,
            )

        if elapsed_sec < position.validation_window_sec:
            return PostEntryDecision(
                triggered=False,
                order_side="sell",
                exit_ratio=0.0,
                reason_code=None,
                unrealized_return_pct=unrealized_return_pct,
            )

        exit_rule = self._expectation_ruleset.evaluate(
            position=position,
            unrealized_return_pct=unrealized_return_pct,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        if exit_rule is not None:
            exit_ratio, reason_code = exit_rule
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=exit_ratio,
                reason_code=reason_code,
                unrealized_return_pct=unrealized_return_pct,
            )

        return PostEntryDecision(
            triggered=False,
            order_side="sell",
            exit_ratio=0.0,
            reason_code=None,
            unrealized_return_pct=unrealized_return_pct,
        )
