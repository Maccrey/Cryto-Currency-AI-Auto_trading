from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.dashboard.overlay import StopLossOverlayService
from app.services.position.exit import PositionExitService
from app.services.position.risk import PositionRiskService
from app.services.position.store import CurrentPositionStore


class PositionRiskPayload(BaseModel):
    current_price: float
    elapsed_sec: int
    momentum_score: float
    orderbook_imbalance: float


def build_position_router(
    *,
    position_store: CurrentPositionStore,
    stop_loss_overlay_service: StopLossOverlayService,
    position_risk_service: PositionRiskService,
    position_exit_service: PositionExitService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/position")

    @router.get("/current")
    def current_position() -> dict[str, object]:
        position = position_store.get()
        if position is None:
            return {
                "status": "empty",
                "position": None,
            }
        return {
            "status": "ok",
            "position": position_store.to_payload(position),
        }

    @router.get("/overlay/stop-loss")
    def stop_loss_overlay() -> dict[str, object]:
        overlay = stop_loss_overlay_service.build(position_store.get())
        return {
            "status": "ok",
            "overlay": {
                "active": overlay.active,
                "market": overlay.market,
                "stop_loss_price": overlay.stop_loss_price,
                "label": overlay.label,
            },
        }

    @router.post("/risk-check")
    def position_risk_check(payload: PositionRiskPayload) -> dict[str, object]:
        return position_risk_service.evaluate(
            current_price=payload.current_price,
            elapsed_sec=payload.elapsed_sec,
            momentum_score=payload.momentum_score,
            orderbook_imbalance=payload.orderbook_imbalance,
        )

    @router.post("/exit")
    def position_exit(payload: PositionRiskPayload) -> dict[str, object]:
        if position_exit_service is None:
            return {
                "status": "not_configured",
                "position": None,
                "trigger": None,
                "execution": None,
            }
        return position_exit_service.evaluate_and_execute(
            current_price=payload.current_price,
            elapsed_sec=payload.elapsed_sec,
            momentum_score=payload.momentum_score,
            orderbook_imbalance=payload.orderbook_imbalance,
        )

    return router
