from __future__ import annotations

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
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self._timestamp_provider = timestamp_provider or (
            lambda: datetime.now().astimezone().isoformat()
        )
        self._prices: dict[str, MarketPriceSnapshot] = {}

    def save(self, *, market: str, price: float) -> MarketPriceSnapshot:
        snapshot = MarketPriceSnapshot(
            market=market,
            price=price,
            recorded_at=self._timestamp_provider(),
        )
        self._prices[market] = snapshot
        return snapshot

    def get(self, market: str) -> MarketPriceSnapshot | None:
        return self._prices.get(market)

    def get_price(self, market: str) -> float | None:
        snapshot = self.get(market)
        return None if snapshot is None else snapshot.price

    @staticmethod
    def to_payload(snapshot: MarketPriceSnapshot) -> dict[str, object]:
        return asdict(snapshot)
