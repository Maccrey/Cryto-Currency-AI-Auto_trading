from __future__ import annotations

from fastapi import APIRouter

from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.recovery.orchestrator import BootState


def build_dashboard_router(
    *,
    boot_state: BootState,
    trading_mode: str,
    learning_enabled: bool,
    dashboard_summary_facade: DashboardSummaryFacade,
    dashboard_market_facade: DashboardMarketFacade,
    dashboard_executions_facade: DashboardExecutionsFacade,
    promotion_dashboard_facade: PromotionDashboardFacade,
) -> APIRouter:
    router = APIRouter(prefix="/dashboard")

    @router.get("/summary")
    def dashboard_summary() -> dict[str, object]:
        return dashboard_summary_facade.build_response(
            boot_state=boot_state,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
        )

    @router.get("/market")
    def dashboard_market(history_limit: int = 20) -> dict[str, object]:
        return dashboard_market_facade.build_current_response(
            history_limit=history_limit,
        )

    @router.get("/executions")
    def dashboard_executions(limit: int = 20) -> dict[str, object]:
        return dashboard_executions_facade.build_history_response(limit=limit)

    @router.get("/promotion")
    def dashboard_promotion() -> dict[str, object]:
        return promotion_dashboard_facade.build_current_response()

    @router.get("/promotion/history")
    def dashboard_promotion_history() -> dict[str, object]:
        return promotion_dashboard_facade.build_history_response()

    return router
