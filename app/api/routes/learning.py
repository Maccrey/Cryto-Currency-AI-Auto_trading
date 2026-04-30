from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.services.learning.diagnostics import LearningLogDiagnostics
from app.services.learning.model_readiness import ModelTrainingReadinessService
from app.services.learning.service import LearningService


def build_learning_router(
    *,
    market: str,
    learning_service: LearningService,
    learning_log_dir: Path | None = None,
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

    @router.get("/diagnostics")
    def learning_diagnostics(tail_limit: int = 2000) -> dict[str, object]:
        if learning_log_dir is None:
            return {
                "status": "not_configured",
                "market": market,
                "diagnostics": None,
            }
        return {
            "status": "ok",
            "market": market,
            "diagnostics": LearningLogDiagnostics(log_dir=learning_log_dir).build(
                tail_limit=tail_limit,
            ),
        }

    @router.get("/model-readiness")
    def model_readiness() -> dict[str, object]:
        if learning_log_dir is None:
            return {
                "status": "not_configured",
                "market": market,
                "readiness": None,
            }
        readiness = ModelTrainingReadinessService(log_dir=learning_log_dir).build()
        return {
            "status": "ok",
            "market": market,
            "readiness": readiness,
        }

    return router
