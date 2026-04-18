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


class PostEntryValidator:
    """Validate whether a freshly opened position is behaving as expected."""

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

        if elapsed_sec < position.validation_window_sec:
            return PostEntryDecision(
                triggered=False,
                order_side="sell",
                exit_ratio=0.0,
                reason_code=None,
                unrealized_return_pct=unrealized_return_pct,
            )

        if unrealized_return_pct < position.min_expected_return_pct:
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=1.0,
                reason_code="STOP_LOSS_EXPECTATION_FAILED",
                unrealized_return_pct=unrealized_return_pct,
            )

        if momentum_score < 0.35:
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=0.5,
                reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
                unrealized_return_pct=unrealized_return_pct,
            )

        if orderbook_imbalance < -0.2:
            return PostEntryDecision(
                triggered=True,
                order_side="sell",
                exit_ratio=0.5,
                reason_code="STOP_LOSS_LIQUIDITY_DROPPED",
                unrealized_return_pct=unrealized_return_pct,
            )

        return PostEntryDecision(
            triggered=False,
            order_side="sell",
            exit_ratio=0.0,
            reason_code=None,
            unrealized_return_pct=unrealized_return_pct,
        )
