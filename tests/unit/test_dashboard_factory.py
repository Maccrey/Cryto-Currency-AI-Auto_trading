from pathlib import Path

from app.services.dashboard.factory import build_dashboard_services
from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.learning_facade import DashboardLearningFacade
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.dashboard.positions_facade import DashboardPositionsFacade
from app.services.dashboard.recovery_facade import DashboardRecoveryFacade
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningService
from app.services.market.store import MarketPriceStore
from app.services.position.ledger import PositionLifecycleLedger
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.state import PromotionStateService
from app.services.recovery.orchestrator import BootState


def test_build_dashboard_services_creates_default_summary_facade(tmp_path: Path) -> None:
    services = build_dashboard_services(
        market="KRW-XRP",
        boot_state=BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=None,
            reconcile_result=None,
        ),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        learning_service=LearningService(log_dir=tmp_path),
        execution_ledger=ExecutionLedger(),
        position_lifecycle_ledger=PositionLifecycleLedger(),
        market_price_store=MarketPriceStore(),
    )

    assert isinstance(services.summary_facade, DashboardSummaryFacade)
    assert isinstance(services.market_facade, DashboardMarketFacade)
    assert isinstance(services.executions_facade, DashboardExecutionsFacade)
    assert isinstance(services.positions_facade, DashboardPositionsFacade)
    assert isinstance(services.learning_facade, DashboardLearningFacade)
    assert isinstance(services.recovery_facade, DashboardRecoveryFacade)


def test_build_dashboard_services_reuses_injected_summary_facade(tmp_path: Path) -> None:
    promotion_facade = PromotionDashboardFacade(
        promotion_state_service=PromotionStateService(),
        promotion_dashboard_service=PromotionDashboardService(),
    )
    summary_facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=promotion_facade,
    )

    services = build_dashboard_services(
        market="KRW-XRP",
        boot_state=BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=None,
            reconcile_result=None,
        ),
        promotion_dashboard_facade=promotion_facade,
        learning_service=LearningService(log_dir=tmp_path),
        execution_ledger=ExecutionLedger(),
        position_lifecycle_ledger=PositionLifecycleLedger(),
        market_price_store=MarketPriceStore(),
        dashboard_summary_facade=summary_facade,
    )

    assert services.summary_facade is summary_facade
