from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionEvaluation:
    status: str
    approved: bool
    rejection_reasons: list[str]


@dataclass(frozen=True)
class PromotionMetrics:
    demo_days: int
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    stoploss_failures: int


class PromotionMetricsAggregator:
    """Aggregate raw demo trade records into promotion metrics."""

    def aggregate(self, *, demo_days: int, trades: list[dict[str, object]]) -> PromotionMetrics:
        total_trades = len(trades)
        wins = [float(trade["pnl"]) for trade in trades if float(trade["pnl"]) > 0]
        losses = [abs(float(trade["pnl"])) for trade in trades if float(trade["pnl"]) < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        stoploss_failures = sum(1 for trade in trades if bool(trade.get("stoploss_failed", False)))

        return PromotionMetrics(
            demo_days=demo_days,
            total_trades=total_trades,
            win_rate=round(win_rate, 3),
            profit_factor=round(profit_factor, 3),
            max_drawdown=self._max_drawdown(trades),
            stoploss_failures=stoploss_failures,
        )

    @staticmethod
    def _max_drawdown(trades: list[dict[str, object]]) -> float:
        peak: float | None = None
        max_drawdown = 0.0
        for trade in trades:
            equity = float(trade["equity"])
            peak = equity if peak is None else max(peak, equity)
            if peak <= 0:
                continue
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        return round(max_drawdown, 3)


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
