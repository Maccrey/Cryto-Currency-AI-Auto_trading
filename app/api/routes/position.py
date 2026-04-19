from __future__ import annotations

from fastapi import APIRouter

from app.services.dashboard.overlay import StopLossOverlayService
from app.services.position.store import CurrentPositionStore


def build_position_router(
    *,
    position_store: CurrentPositionStore,
    stop_loss_overlay_service: StopLossOverlayService,
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

    return router
