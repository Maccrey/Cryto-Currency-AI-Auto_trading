from __future__ import annotations

from dataclasses import dataclass

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision


@dataclass(frozen=True)
class SizingDecision:
    allowed: bool
    order_side: str
    buy_ratio: float
    buy_amount: float
    buy_quantity: float
    blocked_reason: str | None


class SizingEngine:
    """Calculate entry size from signal strength, regime, and cash constraints."""

    BASE_BUY_RATIOS = {
        "weak": 0.08,
        "medium": 0.18,
        "strong": 0.35,
        "very_strong": 0.55,
    }

    def __init__(
        self,
        *,
        min_cash_reserve: float,
        max_spread_bps: float,
        max_slippage_bps: float,
    ) -> None:
        self._min_cash_reserve = min_cash_reserve
        self._max_spread_bps = max_spread_bps
        self._max_slippage_bps = max_slippage_bps

    def size_entry(
        self,
        portfolio: PortfolioState,
        signal: SignalDecision,
        regime: RegimeSnapshot,
        *,
        current_price: float,
        spread_bps: float,
        slippage_bps: float,
    ) -> SizingDecision:
        if signal.blocked:
            return self._blocked("SIGNAL_BLOCKED")
        if not regime.entry_allowed:
            return self._blocked("REGIME_BLOCKED")
        if spread_bps > self._max_spread_bps or slippage_bps > self._max_slippage_bps:
            return self._blocked("SPREAD_OR_SLIPPAGE_LIMIT")

        investable_cash = max(portfolio.cash_balance - self._min_cash_reserve, 0.0)
        if investable_cash <= 0:
            return self._blocked("MIN_CASH_RESERVE")

        base_buy_ratio = self.BASE_BUY_RATIOS[signal.level]
        final_buy_ratio = round(base_buy_ratio * regime.size_multiplier, 3)
        buy_amount = round(investable_cash * final_buy_ratio, 1)
        buy_quantity = round(buy_amount / current_price, 4)

        return SizingDecision(
            allowed=True,
            order_side="buy",
            buy_ratio=final_buy_ratio,
            buy_amount=buy_amount,
            buy_quantity=buy_quantity,
            blocked_reason=None,
        )

    @staticmethod
    def _blocked(reason: str) -> SizingDecision:
        return SizingDecision(
            allowed=False,
            order_side="buy",
            buy_ratio=0.0,
            buy_amount=0.0,
            buy_quantity=0.0,
            blocked_reason=reason,
        )
