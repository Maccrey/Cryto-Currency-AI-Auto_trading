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
    """Decide how to exit when a new position misses post-entry expectations."""

    momentum_reversal_threshold: float = 0.35
    liquidity_dropped_threshold: float = -0.2
    min_adverse_exit_pct: float = 0.01

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
            return (0.5, "STOP_LOSS_MOMENTUM_REVERSAL")

        if orderbook_imbalance < self.liquidity_dropped_threshold:
            return (0.5, "STOP_LOSS_LIQUIDITY_DROPPED")

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
