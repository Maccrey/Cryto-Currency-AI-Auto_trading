from __future__ import annotations

from app.services.dashboard.recovery import DashboardRecoveryService
from app.services.learning.service import LearningService
from app.services.recovery.orchestrator import BootState


class DashboardRecoveryFacade:
    """Provide dashboard-oriented recovery responses."""

    def __init__(
        self,
        *,
        boot_state: BootState,
        learning_service: LearningService,
        dashboard_recovery_service: DashboardRecoveryService,
    ) -> None:
        self._boot_state = boot_state
        self._learning_service = learning_service
        self._dashboard_recovery_service = dashboard_recovery_service

    def build_response(self, *, limit: int = 20) -> dict[str, object]:
        events = self._learning_service.recent_events(limit=limit)
        recovery = self._dashboard_recovery_service.build(
            boot_state=self._boot_state,
            events=events,
        )
        return {
            "status": "ok",
            "recovery": self._dashboard_recovery_service.to_payload(recovery),
        }
