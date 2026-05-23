from __future__ import annotations

from typing import Any, Protocol

from app.services.dashboard.market import DashboardMarketService
from app.services.market.store import MarketPriceStore


class CurrentPriceProvider(Protocol):
    def get_current_price(self, market: str) -> float | None: ...


class DashboardMarketFacade:
    """Provide dashboard-oriented market responses from market state."""

    TREND_HISTORY_LIMIT = 60

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
        self._latest_ticker_meta: dict[str, float] = {}

    def build_current_response(self, *, history_limit: int = 20) -> dict[str, object]:
        snapshot = self._fetch_or_get_snapshot()
        full_history = self._market_price_store.list_history(self._market)
        history = self._chart_history_from(full_history, history_limit=history_limit)
        market = self._dashboard_market_service.build(
            snapshot=snapshot,
            history=history,
            market_price_store=self._market_price_store,
            reference_change_pct=self._latest_ticker_meta.get("signed_change_rate"),
            trend_history=full_history[-self.TREND_HISTORY_LIMIT :],
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
            "summary": {
                **self._dashboard_market_service.to_payload(market),
                **self._latest_ticker_meta,
            },
        }

    def _chart_history(self, *, history_limit: int) -> list:
        history = self._market_price_store.list_history(self._market)
        return self._chart_history_from(history, history_limit=history_limit)

    @staticmethod
    def _chart_history_from(history: list, *, history_limit: int) -> list:
        if history_limit >= len(history):
            return history
        if history_limit < 288:
            return history[-history_limit:]
        return DashboardMarketFacade._sample_history(history, limit=history_limit)

    @staticmethod
    def _sample_history(history: list, *, limit: int) -> list:
        if limit <= 1:
            return history[-limit:]
        last_index = len(history) - 1
        selected = []
        previous_index = -1
        for step in range(limit):
            index = round((step / (limit - 1)) * last_index)
            if index == previous_index:
                continue
            selected.append(history[index])
            previous_index = index
        return selected

    def _fetch_or_get_snapshot(self):
        snapshot = self._market_price_store.get(self._market)
        if self._current_price_provider is None:
            return snapshot
        try:
            price = self._fetch_current_price()
        except Exception:
            return snapshot
        if price is None:
            return snapshot
        if snapshot is not None and snapshot.price == price:
            return snapshot
        return self._market_price_store.save(market=self._market, price=price)

    def _fetch_current_price(self) -> float | None:
        get_current_snapshot = getattr(self._current_price_provider, "get_current_snapshot", None)
        if get_current_snapshot is None:
            return self._current_price_provider.get_current_price(self._market)
        ticker_snapshot = get_current_snapshot(self._market)
        if ticker_snapshot is None:
            return None
        trade_price = float(getattr(ticker_snapshot, "trade_price"))
        self._latest_ticker_meta = self._extract_ticker_meta(ticker_snapshot)
        return trade_price

    @staticmethod
    def _extract_ticker_meta(ticker_snapshot: Any) -> dict[str, float]:
        meta: dict[str, float] = {}
        for attr in ("signed_change_rate", "acc_trade_volume_24h", "acc_trade_price_24h"):
            value = getattr(ticker_snapshot, attr, None)
            if value is not None:
                meta[attr] = float(value)
        return meta
