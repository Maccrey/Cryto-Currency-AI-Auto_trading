from pathlib import Path

from app.services.dashboard.promotion import PromotionDashboardService
from app.services.learning.service import LearningService
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.factory import build_promotion_services
from app.services.promotion.review import PromotionReviewService
from app.services.promotion.runner import PromotionRunner
from app.services.promotion.state import PromotionStateService


def test_build_promotion_services_creates_default_bundle(tmp_path: Path) -> None:
    services = build_promotion_services(
        trading_mode="demo",
        learning_service=LearningService(log_dir=tmp_path),
    )

    assert isinstance(services.runner, PromotionRunner)
    assert isinstance(services.state_service, PromotionStateService)
    assert isinstance(services.dashboard_facade, PromotionDashboardFacade)
    assert isinstance(services.review_service, PromotionReviewService)
    assert services.dashboard_facade.is_ready_for_review() is False


def test_build_promotion_services_reuses_injected_components(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    state_service = PromotionStateService()
    dashboard_facade = PromotionDashboardFacade(
        promotion_state_service=state_service,
        promotion_dashboard_service=PromotionDashboardService(),
    )
    review_service = PromotionReviewService(
        promotion_runner=PromotionRunner.__new__(PromotionRunner),
        promotion_state_service=state_service,
        learning_service=learning_service,
        trading_mode="demo",
    )

    services = build_promotion_services(
        trading_mode="demo",
        learning_service=learning_service,
        promotion_dashboard_facade=dashboard_facade,
        promotion_review_service=review_service,
        promotion_state_service=state_service,
    )

    assert services.state_service is state_service
    assert services.dashboard_facade is dashboard_facade
    assert services.review_service is review_service
