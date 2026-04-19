from __future__ import annotations

from dataclasses import dataclass

from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.promotion.dashboard import PromotionDashboardFacade


@dataclass(frozen=True)
class DashboardServices:
    summary_facade: DashboardSummaryFacade


def build_dashboard_services(
    *,
    promotion_dashboard_facade: PromotionDashboardFacade,
    execution_ledger: ExecutionLedger | None = None,
    dashboard_summary_service: DashboardSummaryService | None = None,
    dashboard_summary_facade: DashboardSummaryFacade | None = None,
) -> DashboardServices:
    summary_service = dashboard_summary_service or DashboardSummaryService()
    summary_facade = dashboard_summary_facade or DashboardSummaryFacade(
        dashboard_summary_service=summary_service,
        promotion_dashboard_facade=promotion_dashboard_facade,
        execution_ledger=execution_ledger,
    )
    return DashboardServices(summary_facade=summary_facade)
