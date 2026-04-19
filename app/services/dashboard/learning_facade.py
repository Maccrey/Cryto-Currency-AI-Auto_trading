from __future__ import annotations

from app.services.dashboard.learning import DashboardLearningService
from app.services.learning.service import LearningService


class DashboardLearningFacade:
    """Provide dashboard-oriented learning event responses."""

    def __init__(
        self,
        *,
        learning_service: LearningService,
        dashboard_learning_service: DashboardLearningService,
    ) -> None:
        self._learning_service = learning_service
        self._dashboard_learning_service = dashboard_learning_service

    def build_response(self, *, limit: int = 20) -> dict[str, object]:
        events = self._learning_service.recent_events(limit=limit)
        learning = self._dashboard_learning_service.build(events=events)
        if learning is None:
            return {
                "status": "empty",
                "learning": None,
            }
        return {
            "status": "ok",
            "learning": self._dashboard_learning_service.to_payload(learning),
        }

    def build_health_response(self, *, limit: int = 50) -> dict[str, object]:
        events = self._learning_service.recent_events(limit=limit)
        learning_health = self._dashboard_learning_service.build_health(events=events)
        if learning_health is None:
            return {
                "status": "empty",
                "health": None,
            }
        return {
            "status": "ok",
            "health": self._dashboard_learning_service.to_health_payload(learning_health),
        }
