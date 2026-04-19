from __future__ import annotations


class MarketPriceStore:
    """Track the latest observed market price for runtime summaries."""

    def __init__(self) -> None:
        self._prices: dict[str, float] = {}

    def save(self, *, market: str, price: float) -> float:
        self._prices[market] = price
        return price

    def get(self, market: str) -> float | None:
        return self._prices.get(market)
