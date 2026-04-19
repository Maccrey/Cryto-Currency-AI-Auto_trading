from app.services.dashboard.factory import build_dashboard_services
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.market.store import MarketPriceStore
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.state import PromotionStateService


def test_build_dashboard_services_creates_default_summary_facade() -> None:
    services = build_dashboard_services(
        market="KRW-XRP",
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        market_price_store=MarketPriceStore(),
    )

    assert isinstance(services.summary_facade, DashboardSummaryFacade)
    assert isinstance(services.market_facade, DashboardMarketFacade)


def test_build_dashboard_services_reuses_injected_summary_facade() -> None:
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
        promotion_dashboard_facade=promotion_facade,
        market_price_store=MarketPriceStore(),
        dashboard_summary_facade=summary_facade,
    )

    assert services.summary_facade is summary_facade
