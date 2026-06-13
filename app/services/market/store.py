from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class MarketPriceSnapshot:
    market: str
    price: float
    recorded_at: str


class MarketPriceStore:
    """Track the latest observed market price for runtime summaries."""

    def __init__(
        self,
        *,
        history_limit: int = 28800,
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self._history_limit = history_limit
        self._timestamp_provider = timestamp_provider or (
            lambda: datetime.now().astimezone().isoformat()
        )
        self._prices: dict[str, MarketPriceSnapshot] = {}
        self._history: dict[str, deque[MarketPriceSnapshot]] = {}

    def save(self, *, market: str, price: float) -> MarketPriceSnapshot:
        return self.save_at(market=market, price=price, recorded_at=self._timestamp_provider())

    def save_at(self, *, market: str, price: float, recorded_at: str) -> MarketPriceSnapshot:
        snapshot = MarketPriceSnapshot(
            market=market,
            price=price,
            recorded_at=recorded_at,
        )
        self._prices[market] = snapshot
        if market not in self._history:
            self._history[market] = deque(maxlen=self._history_limit)
        self._history[market].append(snapshot)
        return snapshot

    def get(self, market: str) -> MarketPriceSnapshot | None:
        return self._prices.get(market)

    def list_history(
        self,
        market: str,
        *,
        limit: int | None = None,
    ) -> list[MarketPriceSnapshot]:
        history = list(self._history.get(market, ()))
        if limit is None or limit >= len(history):
            return history
        return history[-limit:]

    def get_price(self, market: str) -> float | None:
        snapshot = self.get(market)
        return None if snapshot is None else snapshot.price

    def clear(self, market: str | None = None) -> None:
        if market is None:
            self._prices.clear()
            self._history.clear()
            return
        self._prices.pop(market, None)
        self._history.pop(market, None)

    @staticmethod
    def to_payload(snapshot: MarketPriceSnapshot) -> dict[str, object]:
        return asdict(snapshot)

    def history_to_payload(
        self,
        market: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        return [self.to_payload(snapshot) for snapshot in self.list_history(market, limit=limit)]
