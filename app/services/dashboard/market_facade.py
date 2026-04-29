from __future__ import annotations

from typing import Protocol

from app.services.dashboard.market import DashboardMarketService
from app.services.market.store import MarketPriceStore


class CurrentPriceProvider(Protocol):
    def get_current_price(self, market: str) -> float | None: ...


class DashboardMarketFacade:
    """Provide dashboard-oriented market responses from market state."""

    def __init__(
        self,
        *,
        market: str,
        market_price_store: MarketPriceStore,
        dashboard_market_service: DashboardMarketService,
        current_price_provider: CurrentPriceProvider | None = None,
    ) -> None:
        self._market = market
        self._market_price_store = market_price_store
        self._dashboard_market_service = dashboard_market_service
        self._current_price_provider = current_price_provider

    def build_current_response(self, *, history_limit: int = 20) -> dict[str, object]:
        snapshot = self._fetch_or_get_snapshot()
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

    def _fetch_or_get_snapshot(self):
        snapshot = self._market_price_store.get(self._market)
        if self._current_price_provider is None:
            return snapshot
        try:
            price = self._current_price_provider.get_current_price(self._market)
        except Exception:
            return snapshot
        if price is None:
            return snapshot
        return self._market_price_store.save(market=self._market, price=price)
