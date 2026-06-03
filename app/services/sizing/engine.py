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

    def dynamic_ratio_for(self, signal: SignalDecision) -> float:
        return _interpolated_ratio(
            score=signal.score,
            ratios=self.RATIOS,
            inverse=False,
        )


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

    def dynamic_ratio_for(self, signal: SignalDecision) -> float:
        return _interpolated_ratio(
            score=signal.score,
            ratios=self.RATIOS,
            inverse=True,
        )


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

        base_buy_ratio = self._buy_policy.dynamic_ratio_for(signal)
        final_buy_ratio = round(base_buy_ratio * regime.size_multiplier * self._buy_market_state_multiplier(regime), 3)
        buy_amount = round(investable_cash * final_buy_ratio, 1)
        max_fee_adjusted_buy_amount = round(investable_cash / (1 + self._trading_fee_rate), 1)
        buy_amount = min(buy_amount, max_fee_adjusted_buy_amount)
        stop_loss_pct = self._stop_loss_by_signal[signal.level]
        if self._max_stop_loss_risk_amount is not None:
            if self._max_stop_loss_risk_amount <= 0:
                return self._blocked("STOP_LOSS_RISK_LIMIT")
            risk_budget = self._risk_budget_for_buy_ratio(base_buy_ratio)
            buy_amount = min(
                buy_amount,
                round(risk_budget / stop_loss_pct, 1),
            )
        if buy_amount <= 0:
            return self._blocked("STOP_LOSS_RISK_LIMIT")
        if buy_amount < self._order_rules.min_order_amount_krw:
            return self._blocked("MIN_ORDER_AMOUNT")
        buy_quantity = round(buy_amount / current_price, 4)
        sell_ratio = (
            round(self._sell_policy.dynamic_ratio_for(signal) * self._sell_market_state_multiplier(regime), 3)
            if portfolio.asset_balance > 0
            else 0.0
        )
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

    @staticmethod
    def _buy_market_state_multiplier(regime: RegimeSnapshot) -> float:
        if regime.market_state == "bull":
            return 1.08
        if regime.market_state == "bear":
            return 0.55
        if regime.market_state == "box":
            return 0.78
        return 1.0

    def _risk_budget_for_buy_ratio(self, buy_ratio: float) -> float:
        if self._max_stop_loss_risk_amount is None:
            return 0.0
        strongest_ratio = max(self._buy_policy.RATIOS.values())
        if strongest_ratio <= 0:
            return 0.0
        strength_multiplier = max(min(buy_ratio / strongest_ratio, 1.0), 0.0)
        return self._max_stop_loss_risk_amount * strength_multiplier

    @staticmethod
    def _sell_market_state_multiplier(regime: RegimeSnapshot) -> float:
        if regime.market_state == "bull":
            return 0.7
        if regime.market_state == "bear":
            return 1.35
        if regime.market_state == "box":
            return 1.1
        return 1.0


def _interpolated_ratio(
    *,
    score: float,
    ratios: dict[str, float],
    inverse: bool,
) -> float:
    normalized_score = max(min(float(score or 0.0), 1.0), 0.0)
    if inverse:
        normalized_score = 1.0 - normalized_score
    anchors = (
        (0.0, ratios["weak"]),
        (0.4, ratios["medium"]),
        (0.65, ratios["strong"]),
        (0.85, ratios["very_strong"]),
        (1.0, ratios["very_strong"]),
    )
    for (left_score, left_ratio), (right_score, right_ratio) in zip(anchors[:-1], anchors[1:]):
        if normalized_score <= right_score:
            span = right_score - left_score
            if span <= 0:
                return round(right_ratio, 4)
            progress = (normalized_score - left_score) / span
            return round(left_ratio + ((right_ratio - left_ratio) * progress), 4)
    return round(ratios["very_strong"], 4)
