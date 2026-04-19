from __future__ import annotations

from app.services.dashboard.executions import DashboardExecutionsService
from app.services.execution.ledger import ExecutionLedger


class DashboardExecutionsFacade:
    """Provide dashboard-oriented execution history responses."""

    def __init__(
        self,
        *,
        execution_ledger: ExecutionLedger,
        dashboard_executions_service: DashboardExecutionsService,
    ) -> None:
        self._execution_ledger = execution_ledger
        self._dashboard_executions_service = dashboard_executions_service

    def build_history_response(self, *, limit: int = 20) -> dict[str, object]:
        records = self._execution_ledger.list_records()
        if limit < len(records):
            records = records[-limit:]
        history = self._dashboard_executions_service.build_history(records)
        if not history:
            return {
                "status": "empty",
                "history": [],
            }
        return {
            "status": "ok",
            "history": self._dashboard_executions_service.to_history_payload(history),
        }
