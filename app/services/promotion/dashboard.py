from __future__ import annotations

from app.services.dashboard.promotion import PromotionDashboardService
from app.services.promotion.state import PromotionStateService


class PromotionDashboardFacade:
    """Provide dashboard-oriented promotion responses from promotion state."""

    def __init__(
        self,
        *,
        promotion_state_service: PromotionStateService,
        promotion_dashboard_service: PromotionDashboardService,
    ) -> None:
        self._promotion_state_service = promotion_state_service
        self._promotion_dashboard_service = promotion_dashboard_service

    def is_ready_for_review(self) -> bool:
        return self._promotion_state_service.is_ready_for_review()

    def build_current_response(self) -> dict[str, object]:
        promotion = self._promotion_dashboard_service.build_current(
            self._promotion_state_service.get_latest(),
        )
        if promotion is None:
            return {
                "status": "empty",
                "promotion": None,
            }
        return {
            "status": "ok",
            "promotion": self._promotion_dashboard_service.to_payload(promotion),
        }

    def build_history_response(self) -> dict[str, object]:
        history = self._promotion_dashboard_service.build_history(
            self._promotion_state_service.list_history(),
        )
        if not history:
            return {
                "status": "empty",
                "history": [],
            }
        return {
            "status": "ok",
            "history": self._promotion_dashboard_service.to_history_payload(history),
        }
