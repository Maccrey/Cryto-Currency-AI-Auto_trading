from __future__ import annotations

from dataclasses import dataclass, field

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
      기본값 0.015 (1.5%) — 수수료 0.05% × 2 + 여유 마진 포함.
    * ``momentum_reversal_threshold`` – 모멘텀 점수가 이 값 미만이어야
      STOP_LOSS_MOMENTUM_REVERSAL 발동. 너무 높으면 정상적인 횡보 구간에서도
      과민 손절. 기본값 0.20.
    * ``liquidity_dropped_threshold`` – 호가 불균형이 이 값보다 낮을 때
      유동성 소멸 손절 발동. 기본값 -0.2.
    * ``momentum_reversal_requires_imbalance`` – True이면 모멘텀 역전 손절이
      orderbook_imbalance 악화(< orderbook_confirm_threshold)까지 동시 만족해야
      발동. 단독 모멘텀 하락에 의한 과민 손절 방지.
    * ``orderbook_confirm_threshold`` – 모멘텀 역전 손절을 확정하기 위해 필요한
      오더북 불균형 최대값. 기본값 -0.05.
    * ``trailing_stop_activation_pct`` – 이 값 이상 수익을 달성하면 트레일링 스탑
      활성화. 활성화 후 floor 이하로 내려오면 즉시 익절.
    * ``trailing_stop_floor_pct`` – 트레일링 스탑 활성화 후 보장되는 최소 총수익률.
      왕복 수수료와 순수익 여유를 함께 넘어야 한다. 수수료 0.05% × 2인
      기본 환경에서는 0.12%로, 수수료만 남기고 청산되는 것을 막는다.
    """

    momentum_reversal_threshold: float = 0.20   # 강화: 0.35→0.25→0.20 (횡보 오발동 방지)
    liquidity_dropped_threshold: float = -0.2
    min_adverse_exit_pct: float = 0.015          # 강화: 0.8%→1.2%→1.5% (단기 휩소 손절 방지)
    # ── 손절 이중 조건 ────────────────────────────────────────────────────
    momentum_reversal_requires_imbalance: bool = True   # 모멘텀 + 오더북 이중 조건
    orderbook_confirm_threshold: float = -0.05          # 오더북 확인 기준 (-5% 이하)
    # ── 트레일링 스탑 ─────────────────────────────────────────────────────
    trailing_stop_activation_pct: float = 0.006  # 0.6% 수익 달성 시 트레일링 스탑 활성화
    trailing_stop_floor_pct: float = 0.0025       # 왕복 수수료 회수 후 의미 있는 순수익 보호
    trailing_stop_min_retrace_pct: float = 0.0025 # 최고가에서 최소 0.25% 되밀림 확인

    def evaluate(
        self,
        *,
        position: PositionSnapshot,
        unrealized_return_pct: float,
        momentum_score: float,
        orderbook_imbalance: float,
        peak_return_pct: float | None = None,
    ) -> tuple[float, str] | None:
        # ── 1. 익절 목표 달성 ─────────────────────────────────────────────
        if unrealized_return_pct >= position.min_expected_return_pct:
            return (1.0, "TAKE_PROFIT_TARGET_HIT")

        # ── 2. 트레일링 스탑 (수익 구간 진입 후 원금 보호) ─────────────────
        if peak_return_pct is not None and peak_return_pct >= self.trailing_stop_activation_pct:
            if (
                self.trailing_stop_floor_pct <= unrealized_return_pct
                <= peak_return_pct - self.trailing_stop_min_retrace_pct
            ):
                return (1.0, "TRAILING_STOP_TRIGGERED")

        # ── 3. 손실이 임계값 이내이면 관망 ───────────────────────────────
        adverse_exit_pct = self._adverse_exit_pct_for(position.signal_level)
        if unrealized_return_pct > -adverse_exit_pct:
            return None

        # ── 4. 모멘텀 역전 손절 (이중 조건: 모멘텀 + 오더북 확인) ───────────
        if momentum_score < self.momentum_reversal_threshold:
            if self.momentum_reversal_requires_imbalance:
                # 오더북 불균형이 동시에 악화된 경우에만 손절 발동
                if orderbook_imbalance < self.orderbook_confirm_threshold:
                    return (1.0, "STOP_LOSS_MOMENTUM_REVERSAL")
                # 모멘텀만 낮고 오더북은 아직 양호 → 관망 유지
                return None
            return (1.0, "STOP_LOSS_MOMENTUM_REVERSAL")

        # ── 5. 유동성 소멸 손절 (오더북 단독 기준) ────────────────────────
        if orderbook_imbalance < self.liquidity_dropped_threshold:
            return (1.0, "STOP_LOSS_LIQUIDITY_DROPPED")

        return None

    def _adverse_exit_pct_for(self, signal_level: str | None) -> float:
        if signal_level == "weak":
            return min(self.min_adverse_exit_pct, 0.008)
        if signal_level == "medium":
            return min(self.min_adverse_exit_pct, 0.012)
        if signal_level == "strong":
            return min(self.min_adverse_exit_pct, 0.018)
        if signal_level == "very_strong":
            return max(self.min_adverse_exit_pct, 0.022)
        return self.min_adverse_exit_pct


class PostEntryValidator:
    """Validate whether a freshly opened position is behaving as expected.

    트레일링 스탑을 위해 포지션별 최고 수익률(peak_return_pct)을 추적합니다.
    포지션이 교체되면 반드시 reset()을 호출해 상태를 초기화해야 합니다.
    """

    def __init__(
        self,
        *,
        expectation_ruleset: PostEntryExpectationRuleset | None = None,
    ) -> None:
        self._expectation_ruleset = expectation_ruleset or PostEntryExpectationRuleset()
        self._peak_return_pct: float | None = None   # 트레일링 스탑용 최고 수익률

    def reset(self) -> None:
        """포지션이 청산되면 최고 수익률 상태를 초기화합니다."""
        self._peak_return_pct = None

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

        # ── 최고 수익률 갱신 (트레일링 스탑용) ─────────────────────────────
        if self._peak_return_pct is None or unrealized_return_pct > self._peak_return_pct:
            self._peak_return_pct = unrealized_return_pct

        # ── 익절 목표 달성 (validation window 무관하게 즉시) ─────────────
        if unrealized_return_pct >= position.min_expected_return_pct:
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=1.0,
                reason_code="TAKE_PROFIT_TARGET_HIT",
                unrealized_return_pct=unrealized_return_pct,
            )

        # ── 트레일링 스탑 (validation window 이후, 수익 달성 후 하락 시) ──
        ruleset = self._expectation_ruleset
        if (
            self._peak_return_pct is not None
            and self._peak_return_pct >= ruleset.trailing_stop_activation_pct
            and ruleset.trailing_stop_floor_pct <= unrealized_return_pct
            <= self._peak_return_pct - ruleset.trailing_stop_min_retrace_pct
        ):
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=1.0,
                reason_code="TRAILING_STOP_TRIGGERED",
                unrealized_return_pct=unrealized_return_pct,
            )

        # ── validation window 이내이면 관망 ────────────────────────────
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
            peak_return_pct=self._peak_return_pct,
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
