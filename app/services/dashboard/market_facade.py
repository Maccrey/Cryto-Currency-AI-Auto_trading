from __future__ import annotations

from app.services.dashboard.market import DashboardMarketService
from app.services.market.store import MarketPriceStore


class DashboardMarketFacade:
    """Provide dashboard-oriented market responses from market state."""

    def __init__(
        self,
        *,
        market: str,
        market_price_store: MarketPriceStore,
        dashboard_market_service: DashboardMarketService,
    ) -> None:
        self._market = market
        self._market_price_store = market_price_store
        self._dashboard_market_service = dashboard_market_service

    def build_current_response(self, *, history_limit: int = 20) -> dict[str, object]:
        snapshot = self._market_price_store.get(self._market)
        history = self._market_price_store.list_history(self._market, limit=history_limit)
        market = self._dashboard_market_service.build(
            snapshot=snapshot,
            history=history,
            market_price_store=self._market_price_store,
        )
        if market is None:
            return {
                "status": "empty",
                "market": self._market,
                "summary": None,
            }
        return {
            "status": "ok",
            "market": self._market,
            "summary": self._dashboard_market_service.to_payload(market),
        }
