from __future__ import annotations

from dataclasses import dataclass

from app.integrations.telegram.lifecycle_notification_dispatcher import (
    LifecycleNotificationDispatcher,
)
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.learning.service import LearningService
from app.services.promotion.approval import PromotionApprovalFlow
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.evaluator import PromotionEvaluator
from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.lifecycle import PromotionLifecycleService
from app.services.promotion.review import PromotionReviewService
from app.services.promotion.runner import PromotionRunner
from app.services.promotion.state import PromotionStateService
from app.services.promotion.status import PromotionStatusStore


@dataclass(frozen=True)
class PromotionServices:
    runner: PromotionRunner
    state_service: PromotionStateService
    dashboard_facade: PromotionDashboardFacade
    review_service: PromotionReviewService


def build_promotion_services(
    *,
    trading_mode: str,
    learning_service: LearningService,
    promotion_runner: PromotionRunner | None = None,
    promotion_dashboard_service: PromotionDashboardService | None = None,
    promotion_review_service: PromotionReviewService | None = None,
    promotion_dashboard_facade: PromotionDashboardFacade | None = None,
    promotion_state_service: PromotionStateService | None = None,
    promotion_history_store: PromotionHistoryStore | None = None,
    promotion_status_store: PromotionStatusStore | None = None,
) -> PromotionServices:
    runner = promotion_runner or PromotionRunner(
        lifecycle_service=PromotionLifecycleService(
            evaluator=PromotionEvaluator(
                min_demo_days=14,
                min_trades=100,
                min_profit_factor=1.2,
                max_drawdown=0.08,
                max_stoploss_failures=0,
            ),
            approval_flow=PromotionApprovalFlow(),
            notification_dispatcher=LifecycleNotificationDispatcher(),
        ),
    )
    state_service = promotion_state_service or PromotionStateService(
        status_store=promotion_status_store,
        history_store=promotion_history_store,
    )
    dashboard_service = promotion_dashboard_service or PromotionDashboardService()
    dashboard_facade = promotion_dashboard_facade or PromotionDashboardFacade(
        promotion_state_service=state_service,
        promotion_dashboard_service=dashboard_service,
    )
    review_service = promotion_review_service or PromotionReviewService(
        promotion_runner=runner,
        promotion_state_service=state_service,
        learning_service=learning_service,
        trading_mode=trading_mode,
    )
    return PromotionServices(
        runner=runner,
        state_service=state_service,
        dashboard_facade=dashboard_facade,
        review_service=review_service,
    )
