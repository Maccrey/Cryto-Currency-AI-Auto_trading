from __future__ import annotations

from fastapi import APIRouter

from app.services.learning.service import LearningService


def build_learning_router(
    *,
    market: str,
    learning_service: LearningService,
) -> APIRouter:
    router = APIRouter(prefix="/learning")

    @router.get("/recent")
    def recent_learning_events(limit: int = 20) -> dict[str, object]:
        events = learning_service.recent_events_payload(limit=limit)
        if not events:
            return {
                "status": "empty",
                "market": market,
                "events": [],
            }

        return {
            "status": "ok",
            "market": market,
            "events": events,
        }

    return router
