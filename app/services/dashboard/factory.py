from __future__ import annotations

from dataclasses import dataclass

from app.services.dashboard.executions import DashboardExecutionsService
from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.market import DashboardMarketService
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.market.store import MarketPriceStore
from app.services.position.store import CurrentPositionStore
from app.services.promotion.dashboard import PromotionDashboardFacade


@dataclass(frozen=True)
class DashboardServices:
    summary_facade: DashboardSummaryFacade
    market_facade: DashboardMarketFacade
    executions_facade: DashboardExecutionsFacade


def build_dashboard_services(
    *,
    market: str,
    promotion_dashboard_facade: PromotionDashboardFacade,
    execution_ledger: ExecutionLedger | None = None,
    position_store: CurrentPositionStore | None = None,
    market_price_store: MarketPriceStore | None = None,
    dashboard_summary_service: DashboardSummaryService | None = None,
    dashboard_market_service: DashboardMarketService | None = None,
    dashboard_executions_service: DashboardExecutionsService | None = None,
    dashboard_summary_facade: DashboardSummaryFacade | None = None,
    dashboard_market_facade: DashboardMarketFacade | None = None,
    dashboard_executions_facade: DashboardExecutionsFacade | None = None,
) -> DashboardServices:
    summary_service = dashboard_summary_service or DashboardSummaryService()
    market_service = dashboard_market_service or DashboardMarketService()
    executions_service = dashboard_executions_service or DashboardExecutionsService()
    summary_facade = dashboard_summary_facade or DashboardSummaryFacade(
        dashboard_summary_service=summary_service,
        promotion_dashboard_facade=promotion_dashboard_facade,
        execution_ledger=execution_ledger,
        position_store=position_store,
        market_price_store=market_price_store,
    )
    if market_price_store is None:
        raise ValueError("market_price_store is required to build dashboard services")
    market_facade = dashboard_market_facade or DashboardMarketFacade(
        market=market,
        market_price_store=market_price_store,
        dashboard_market_service=market_service,
    )
    if execution_ledger is None:
        raise ValueError("execution_ledger is required to build dashboard services")
    executions_facade = dashboard_executions_facade or DashboardExecutionsFacade(
        execution_ledger=execution_ledger,
        dashboard_executions_service=executions_service,
    )
    return DashboardServices(
        summary_facade=summary_facade,
        market_facade=market_facade,
        executions_facade=executions_facade,
    )
