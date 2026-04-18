from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionEvaluation:
    status: str
    approved: bool
    rejection_reasons: list[str]


class PromotionEvaluator:
    """Evaluate whether demo performance is sufficient for live review."""

    def __init__(
        self,
        *,
        min_demo_days: int,
        min_trades: int,
        min_profit_factor: float,
        max_drawdown: float,
        max_stoploss_failures: int,
    ) -> None:
        self._min_demo_days = min_demo_days
        self._min_trades = min_trades
        self._min_profit_factor = min_profit_factor
        self._max_drawdown = max_drawdown
        self._max_stoploss_failures = max_stoploss_failures

    def evaluate(
        self,
        *,
        demo_days: int,
        total_trades: int,
        profit_factor: float,
        max_drawdown: float,
        stoploss_failures: int,
    ) -> PromotionEvaluation:
        rejection_reasons: list[str] = []

        if demo_days < self._min_demo_days:
            rejection_reasons.append("DEMO_DAYS_BELOW_THRESHOLD")
        if total_trades < self._min_trades:
            rejection_reasons.append("TRADE_COUNT_BELOW_THRESHOLD")
        if profit_factor < self._min_profit_factor:
            rejection_reasons.append("PROFIT_FACTOR_BELOW_THRESHOLD")
        if max_drawdown > self._max_drawdown:
            rejection_reasons.append("MAX_DRAWDOWN_ABOVE_THRESHOLD")
        if stoploss_failures > self._max_stoploss_failures:
            rejection_reasons.append("STOPLOSS_FAILURES_ABOVE_THRESHOLD")

        if rejection_reasons:
            return PromotionEvaluation(
                status="NOT_READY",
                approved=False,
                rejection_reasons=rejection_reasons,
            )

        return PromotionEvaluation(
            status="READY_FOR_REVIEW",
            approved=False,
            rejection_reasons=[],
        )
