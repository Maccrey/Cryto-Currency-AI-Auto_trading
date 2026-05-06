from __future__ import annotations

from dataclasses import dataclass

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.execution.rules import UpbitOrderRules
from app.services.signals.engine import SignalDecision


@dataclass(frozen=True)
class SizingDecision:
    allowed: bool
    order_side: str
    buy_ratio: float
    buy_amount: float
    buy_quantity: float
    sell_ratio: float = 0.0
    sell_amount: float = 0.0
    sell_quantity: float = 0.0
    stop_loss_price: float | None = None
    blocked_reason: str | None = None


class BuySizingPolicy:
    """Strength-to-buy-ratio policy for entry sizing."""

    RATIOS = {
        "weak": 0.08,
        "medium": 0.18,
        "strong": 0.35,
        "very_strong": 0.55,
    }

    def ratio_for(self, signal_level: str) -> float:
        return self.RATIOS[signal_level]


class SellSizingPolicy:
    """Strength-to-sell-ratio policy for exit sizing."""

    RATIOS = {
        "weak": 0.12,
        "medium": 0.28,
        "strong": 0.45,
        "very_strong": 0.70,
    }

    def ratio_for(self, signal_level: str) -> float:
        return self.RATIOS[signal_level]


class SizingEngine:
    """Calculate entry size from signal strength, regime, and cash constraints."""

    def __init__(
        self,
        *,
        min_cash_reserve: float,
        max_spread_bps: float,
        max_slippage_bps: float,
        max_stop_loss_risk_amount: float | None = None,
        trading_fee_rate: float = 0.0005,
        min_net_edge_pct: float = 0.0008,
        min_order_amount_krw: float = 5_000.0,
        order_rules: UpbitOrderRules | None = None,
        buy_policy: BuySizingPolicy | None = None,
        sell_policy: SellSizingPolicy | None = None,
        stop_loss_by_signal: dict[str, float] | None = None,
    ) -> None:
        self._min_cash_reserve = min_cash_reserve
        self._max_spread_bps = max_spread_bps
        self._max_slippage_bps = max_slippage_bps
        self._max_stop_loss_risk_amount = max_stop_loss_risk_amount
        self._trading_fee_rate = trading_fee_rate
        self._min_net_edge_pct = min_net_edge_pct
        self._order_rules = order_rules or UpbitOrderRules(
            min_order_amount_krw=min_order_amount_krw,
        )
        self._buy_policy = buy_policy or BuySizingPolicy()
        self._sell_policy = sell_policy or SellSizingPolicy()
        self._stop_loss_by_signal = stop_loss_by_signal or {
            "weak": 0.030,
            "medium": 0.030,
            "strong": 0.030,
            "very_strong": 0.030,
        }

    def size_entry(
        self,
        portfolio: PortfolioState,
        signal: SignalDecision,
        regime: RegimeSnapshot,
        *,
        current_price: float,
        spread_bps: float,
        slippage_bps: float,
        relax_fee_edge: bool = False,
    ) -> SizingDecision:
        if signal.blocked:
            return self._blocked("SIGNAL_BLOCKED")
        if not regime.entry_allowed:
            return self._blocked("REGIME_BLOCKED")
        if spread_bps > self._max_spread_bps or slippage_bps > self._max_slippage_bps:
            return self._blocked("SPREAD_OR_SLIPPAGE_LIMIT")
        if current_price <= 0:
            return self._blocked("INVALID_CURRENT_PRICE")
        edge_buffer = self._min_net_edge_pct
        if signal.level == "medium":
            edge_buffer *= 0.25
        if not relax_fee_edge and self._estimated_edge_pct(signal) <= self._round_trip_fee_pct() + edge_buffer:
            return self._blocked("FEE_ADJUSTED_EDGE_LIMIT")

        investable_cash = max(portfolio.cash_balance - self._min_cash_reserve, 0.0)
        if investable_cash <= 0:
            return self._blocked("MIN_CASH_RESERVE")

        base_buy_ratio = self._buy_policy.ratio_for(signal.level)
        final_buy_ratio = round(base_buy_ratio * regime.size_multiplier, 3)
        buy_amount = round(investable_cash * final_buy_ratio, 1)
        max_fee_adjusted_buy_amount = round(investable_cash / (1 + self._trading_fee_rate), 1)
        buy_amount = min(buy_amount, max_fee_adjusted_buy_amount)
        stop_loss_pct = self._stop_loss_by_signal[signal.level]
        if self._max_stop_loss_risk_amount is not None:
            if self._max_stop_loss_risk_amount <= 0:
                return self._blocked("STOP_LOSS_RISK_LIMIT")
            buy_amount = min(
                buy_amount,
                round(self._max_stop_loss_risk_amount / stop_loss_pct, 1),
            )
        if buy_amount <= 0:
            return self._blocked("STOP_LOSS_RISK_LIMIT")
        if buy_amount < self._order_rules.min_order_amount_krw:
            return self._blocked("MIN_ORDER_AMOUNT")
        buy_quantity = round(buy_amount / current_price, 4)
        sell_ratio = self._sell_policy.ratio_for(signal.level) if portfolio.asset_balance > 0 else 0.0
        sell_quantity = round(portfolio.asset_balance * sell_ratio, 8)
        sell_amount = round(sell_quantity * current_price, 1)
        stop_loss_price = round(
            current_price * (1 - stop_loss_pct),
            4,
        )

        return SizingDecision(
            allowed=True,
            order_side="buy",
            buy_ratio=final_buy_ratio,
            buy_amount=buy_amount,
            buy_quantity=buy_quantity,
            sell_ratio=sell_ratio,
            sell_amount=sell_amount,
            sell_quantity=sell_quantity,
            stop_loss_price=stop_loss_price,
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

    def _round_trip_fee_pct(self) -> float:
        return self._trading_fee_rate * 2

    @staticmethod
    def _estimated_edge_pct(signal: SignalDecision) -> float:
        if signal.level == "very_strong":
            return max(0.0045, signal.score * 0.005)
        if signal.level == "strong":
            return max(0.0025, signal.score * 0.004)
        if signal.level == "medium":
            return max(0.00135, signal.score * 0.003)
        return max(0.0, signal.score * 0.001)
