from __future__ import annotations

from fastapi import APIRouter

from app.services.market.store import MarketPriceStore


def build_market_router(
    *,
    market: str,
    market_price_store: MarketPriceStore,
) -> APIRouter:
    router = APIRouter(prefix="/market")

    @router.get("/current")
    def current_market_price() -> dict[str, object]:
        snapshot = market_price_store.get(market)
        if snapshot is None:
            return {
                "status": "empty",
                "market": market,
                "snapshot": None,
            }
        return {
            "status": "ok",
            "market": market,
            "snapshot": market_price_store.to_payload(snapshot),
        }

    @router.get("/history")
    def market_price_history(limit: int = 20) -> dict[str, object]:
        history = market_price_store.history_to_payload(market, limit=limit)
        if not history:
            return {
                "status": "empty",
                "market": market,
                "history": [],
            }
        return {
            "status": "ok",
            "market": market,
            "history": history,
        }

    return router
