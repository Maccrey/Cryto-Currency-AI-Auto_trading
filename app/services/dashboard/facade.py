from __future__ import annotations

from app.services.execution.ledger import ExecutionLedger
from app.services.dashboard.summary import DashboardSummaryService
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.recovery.orchestrator import BootState


class DashboardSummaryFacade:
    """Compose dashboard summary payloads from runtime and promotion state."""

    def __init__(
        self,
        *,
        dashboard_summary_service: DashboardSummaryService,
        promotion_dashboard_facade: PromotionDashboardFacade,
        execution_ledger: ExecutionLedger | None = None,
    ) -> None:
        self._dashboard_summary_service = dashboard_summary_service
        self._promotion_dashboard_facade = promotion_dashboard_facade
        self._execution_ledger = execution_ledger

    def build_response(
        self,
        *,
        boot_state: BootState,
        trading_mode: str,
        learning_enabled: bool,
    ) -> dict[str, object]:
        ledger_summary = None if self._execution_ledger is None else self._execution_ledger.summarize()
        summary = self._dashboard_summary_service.build(
            boot_state=boot_state,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
            realized_pnl=0.0 if ledger_summary is None else ledger_summary.realized_pnl,
            unrealized_pnl=0.0,
            buy_count=0 if ledger_summary is None else ledger_summary.buy_count,
            sell_count=0 if ledger_summary is None else ledger_summary.sell_count,
            stop_loss_count=0 if ledger_summary is None else ledger_summary.stop_loss_count,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
            promotion_ready=self._promotion_dashboard_facade.is_ready_for_review(),
        )
        if isinstance(summary, dict):
            return summary
        return self._dashboard_summary_service.to_payload(summary)
