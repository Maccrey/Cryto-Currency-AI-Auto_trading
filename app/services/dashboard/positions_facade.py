from __future__ import annotations

from app.services.dashboard.positions import DashboardPositionsService
from app.services.position.ledger import PositionLifecycleLedger


class DashboardPositionsFacade:
    """Provide dashboard-oriented position lifecycle responses."""

    def __init__(
        self,
        *,
        position_lifecycle_ledger: PositionLifecycleLedger,
        dashboard_positions_service: DashboardPositionsService,
    ) -> None:
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._dashboard_positions_service = dashboard_positions_service

    def build_history_response(self, *, limit: int = 20) -> dict[str, object]:
        records = self._position_lifecycle_ledger.list_records(limit=limit)
        history = self._dashboard_positions_service.build_history(records)
        if not history:
            return {
                "status": "empty",
                "history": [],
            }
        return {
            "status": "ok",
            "history": self._dashboard_positions_service.to_history_payload(history),
        }
