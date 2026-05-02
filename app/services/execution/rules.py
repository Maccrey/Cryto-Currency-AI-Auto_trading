from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpbitOrderRules:
    """Exchange order constraints that must be enforced before execution."""

    min_order_amount_krw: float = 5_000.0

    def applies_to_market(self, market: str) -> bool:
        return market.upper().startswith("KRW-")

    def notional(self, *, price: float, quantity: float) -> float:
        return max(float(price), 0.0) * max(float(quantity), 0.0)

    def is_allowed(self, *, market: str, price: float, quantity: float) -> bool:
        if not self.applies_to_market(market):
            return True
        return self.notional(price=price, quantity=quantity) >= self.min_order_amount_krw
