from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.promotion.review import PromotionReviewService
from app.services.promotion.state import PromotionStateService


class PromotionReviewPayload(BaseModel):
    market: str
    demo_days: int
    total_trades: int
    profit_factor: float
    max_drawdown: float
    stoploss_failures: int
    approval_granted: bool
    approved_by: str
    activated_at: str


def build_promotion_router(
    *,
    promotion_review_service: PromotionReviewService,
    promotion_state_service: PromotionStateService,
) -> APIRouter:
    router = APIRouter(prefix="/promotion")

    @router.post("/review")
    def promotion_review(payload: PromotionReviewPayload) -> dict[str, object]:
        return promotion_review_service.review(
            promotion_review_service.build_command(payload.model_dump()),
        )

    @router.get("/status")
    def promotion_status() -> dict[str, object]:
        return promotion_state_service.build_status_response()

    @router.get("/history")
    def promotion_history() -> dict[str, object]:
        return promotion_state_service.build_history_response()

    return router
