from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.market.store import MarketPriceSnapshot, MarketPriceStore


@dataclass(frozen=True)
class DashboardMarket:
    market: str
    current_price: float
    recorded_at: str
    recent_change_pct: float
    history: list[dict[str, object]]


class DashboardMarketService:
    """Build dashboard-friendly market state payloads."""

    def build(
        self,
        *,
        snapshot: MarketPriceSnapshot | None,
        history: list[MarketPriceSnapshot],
        market_price_store: MarketPriceStore,
    ) -> DashboardMarket | None:
        if snapshot is None:
            return None

        recent_change_pct = 0.0
        if len(history) >= 2 and history[0].price > 0:
            recent_change_pct = round(
                (snapshot.price - history[0].price) / history[0].price,
                4,
            )

        return DashboardMarket(
            market=snapshot.market,
            current_price=snapshot.price,
            recorded_at=snapshot.recorded_at,
            recent_change_pct=recent_change_pct,
            history=[market_price_store.to_payload(item) for item in history],
        )

    @staticmethod
    def to_payload(market: DashboardMarket) -> dict[str, object]:
        return asdict(market)
