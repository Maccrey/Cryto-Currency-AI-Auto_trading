from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.portfolio.sync import PortfolioState
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService


class PortfolioPayload(BaseModel):
    cash_balance: float
    asset_currency: str
    asset_balance: float
    avg_buy_price: float


class TradeDecisionPayload(BaseModel):
    prices: list[float]
    traded_values: list[float]
    spread_bps: float
    orderbook_imbalance: float
    liquidity_score: float
    regime_score: float
    current_price: float
    slippage_bps: float
    portfolio: PortfolioPayload
    safe_mode: bool = False
    recent_loss_streak: int = 0


def build_decision_router(
    *,
    trade_decision_service: TradeDecisionService,
) -> APIRouter:
    router = APIRouter(prefix="/decision")

    @router.post("/entry")
    def evaluate_entry(payload: TradeDecisionPayload) -> dict[str, object]:
        result = trade_decision_service.evaluate(
            TradeDecisionRequest(
                prices=payload.prices,
                traded_values=payload.traded_values,
                spread_bps=payload.spread_bps,
                orderbook_imbalance=payload.orderbook_imbalance,
                liquidity_score=payload.liquidity_score,
                regime_score=payload.regime_score,
                current_price=payload.current_price,
                slippage_bps=payload.slippage_bps,
                portfolio=PortfolioState(**payload.portfolio.model_dump()),
                safe_mode=payload.safe_mode,
                recent_loss_streak=payload.recent_loss_streak,
            ),
        )
        return {
            "status": "ok",
            "decision": trade_decision_service.to_payload(result),
        }

    return router
