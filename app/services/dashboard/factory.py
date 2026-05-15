from __future__ import annotations

from dataclasses import dataclass

from app.services.dashboard.executions import DashboardExecutionsService
from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.learning import DashboardLearningService
from app.services.dashboard.learning_facade import DashboardLearningFacade
from app.services.dashboard.market import DashboardMarketService
from app.services.dashboard.market_facade import CurrentPriceProvider, DashboardMarketFacade
from app.services.dashboard.positions import DashboardPositionsService
from app.services.dashboard.positions_facade import DashboardPositionsFacade
from app.services.dashboard.recovery import DashboardRecoveryService
from app.services.dashboard.recovery_facade import DashboardRecoveryFacade
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningService
from app.services.market.store import MarketPriceStore
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.promotion.dashboard import PromotionDashboardFacade


@dataclass(frozen=True)
class DashboardServices:
    summary_facade: DashboardSummaryFacade
    market_facade: DashboardMarketFacade
    executions_facade: DashboardExecutionsFacade
    positions_facade: DashboardPositionsFacade
    learning_facade: DashboardLearningFacade
    recovery_facade: DashboardRecoveryFacade


def build_dashboard_services(
    *,
    market: str,
    boot_state,
    promotion_dashboard_facade: PromotionDashboardFacade,
    learning_service: LearningService,
    execution_ledger: ExecutionLedger | None = None,
    position_lifecycle_ledger: PositionLifecycleLedger | None = None,
    position_store: CurrentPositionStore | None = None,
    market_price_store: MarketPriceStore | None = None,
    current_price_provider: CurrentPriceProvider | None = None,
    dashboard_summary_service: DashboardSummaryService | None = None,
    dashboard_market_service: DashboardMarketService | None = None,
    dashboard_executions_service: DashboardExecutionsService | None = None,
    dashboard_positions_service: DashboardPositionsService | None = None,
    dashboard_learning_service: DashboardLearningService | None = None,
    dashboard_recovery_service: DashboardRecoveryService | None = None,
    dashboard_summary_facade: DashboardSummaryFacade | None = None,
    dashboard_market_facade: DashboardMarketFacade | None = None,
    dashboard_executions_facade: DashboardExecutionsFacade | None = None,
    dashboard_positions_facade: DashboardPositionsFacade | None = None,
    dashboard_learning_facade: DashboardLearningFacade | None = None,
    dashboard_recovery_facade: DashboardRecoveryFacade | None = None,
) -> DashboardServices:
    summary_service = dashboard_summary_service or DashboardSummaryService()
    market_service = dashboard_market_service or DashboardMarketService(
        learning_service=learning_service,
    )
    executions_service = dashboard_executions_service or DashboardExecutionsService()
    positions_service = dashboard_positions_service or DashboardPositionsService()
    learning_dashboard_service = dashboard_learning_service or DashboardLearningService()
    recovery_service = dashboard_recovery_service or DashboardRecoveryService()
    summary_facade = dashboard_summary_facade or DashboardSummaryFacade(
        dashboard_summary_service=summary_service,
        promotion_dashboard_facade=promotion_dashboard_facade,
        learning_service=learning_service,
        execution_ledger=execution_ledger,
        position_lifecycle_ledger=position_lifecycle_ledger,
        position_store=position_store,
        market_price_store=market_price_store,
    )
    if market_price_store is None:
        raise ValueError("market_price_store is required to build dashboard services")
    market_facade = dashboard_market_facade or DashboardMarketFacade(
        market=market,
        market_price_store=market_price_store,
        dashboard_market_service=market_service,
        current_price_provider=current_price_provider,
    )
    if execution_ledger is None:
        raise ValueError("execution_ledger is required to build dashboard services")
    executions_facade = dashboard_executions_facade or DashboardExecutionsFacade(
        execution_ledger=execution_ledger,
        dashboard_executions_service=executions_service,
    )
    if position_lifecycle_ledger is None:
        raise ValueError("position_lifecycle_ledger is required to build dashboard services")
    positions_facade = dashboard_positions_facade or DashboardPositionsFacade(
        position_lifecycle_ledger=position_lifecycle_ledger,
        dashboard_positions_service=positions_service,
    )
    learning_facade = dashboard_learning_facade or DashboardLearningFacade(
        learning_service=learning_service,
        dashboard_learning_service=learning_dashboard_service,
    )
    recovery_facade = dashboard_recovery_facade or DashboardRecoveryFacade(
        boot_state=boot_state,
        learning_service=learning_service,
        dashboard_recovery_service=recovery_service,
    )
    return DashboardServices(
        summary_facade=summary_facade,
        market_facade=market_facade,
        executions_facade=executions_facade,
        positions_facade=positions_facade,
        learning_facade=learning_facade,
        recovery_facade=recovery_facade,
    )
