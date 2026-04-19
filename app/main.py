from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.logging import configure_logging
from app.core.settings import load_settings
from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.lifecycle_notification_dispatcher import (
    LifecycleNotificationDispatcher,
)
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.learning.service import LearningService
from app.services.portfolio.sync import PortfolioSyncService
from app.services.promotion.approval import PromotionApprovalFlow
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.evaluator import PromotionEvaluator
from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.lifecycle import PromotionLifecycleService
from app.services.promotion.review import PromotionReviewService
from app.services.promotion.runner import PromotionRunner
from app.services.promotion.state import PromotionStateService
from app.services.promotion.status import PromotionStatusStore
from app.services.recovery.hard_stop import RestartCounter
from app.services.recovery.orchestrator import (
    InMemoryRestartStore,
    RecoveryOrchestrator,
)
from app.services.recovery.open_orders import OpenOrderReconciler


class PromotionReviewPayload(BaseModel):
    market: str
    demo_days: int
    total_trades: int
    profit_factor: float
    max_drawdown: float
    stoploss_failures: int
    approval_granted: bool
    approved_by: str
    activated_at: str


def create_app(
    recovery_orchestrator: RecoveryOrchestrator | None = None,
    promotion_dashboard_service: PromotionDashboardService | None = None,
    dashboard_summary_service: DashboardSummaryService | None = None,
    learning_service: LearningService | None = None,
    promotion_runner: PromotionRunner | None = None,
    promotion_dashboard_facade: PromotionDashboardFacade | None = None,
    promotion_review_service: PromotionReviewService | None = None,
    promotion_state_service: PromotionStateService | None = None,
    promotion_history_store: PromotionHistoryStore | None = None,
    promotion_status_store: PromotionStatusStore | None = None,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    hard_stop_notifier: HardStopNotifier | None = None,
    timestamp_provider: Callable[[], str] | None = None,
) -> FastAPI:
    settings = load_settings()
    configure_logging(settings.learning_log_dir)
    timestamp_provider = timestamp_provider or (lambda: datetime.now().astimezone().isoformat())

    app = FastAPI(title=settings.app_name)
    if recovery_orchestrator is None:
        upbit_client = UpbitRestClient(
            base_url=settings.upbit_base_url,
            auth_signer=UpbitAuthSigner(
                access_key=settings.upbit_access_key,
                secret_key=settings.upbit_secret_key,
            ),
        )
        recovery_orchestrator = RecoveryOrchestrator(
            app_name=settings.app_name,
            trading_mode=settings.trading_mode,
            portfolio_sync_service=PortfolioSyncService(
                upbit_client=upbit_client,
                trade_coin=settings.trade_coin,
            ),
            open_order_reconciler=OpenOrderReconciler(
                upbit_client=upbit_client,
                trade_market=settings.trade_market,
            ),
            restart_store=InMemoryRestartStore(),
            restart_counter=RestartCounter(threshold=3),
        )
    if dashboard_summary_service is None:
        dashboard_summary_service = DashboardSummaryService()
    if promotion_dashboard_service is None:
        promotion_dashboard_service = PromotionDashboardService()
    if learning_service is None:
        learning_service = LearningService(log_dir=settings.learning_log_dir)
    if boot_notification_dispatcher is None and hard_stop_notifier is not None:
        boot_notification_dispatcher = BootNotificationDispatcher(
            hard_stop_notifier=hard_stop_notifier,
        )
    if promotion_runner is None:
        promotion_runner = PromotionRunner(
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
    if promotion_state_service is None:
        promotion_state_service = PromotionStateService(
            status_store=promotion_status_store,
            history_store=promotion_history_store,
        )
    if promotion_dashboard_facade is None:
        promotion_dashboard_facade = PromotionDashboardFacade(
            promotion_state_service=promotion_state_service,
            promotion_dashboard_service=promotion_dashboard_service,
        )
    if promotion_review_service is None:
        promotion_review_service = PromotionReviewService(
            promotion_runner=promotion_runner,
            promotion_state_service=promotion_state_service,
            learning_service=learning_service,
            trading_mode=settings.trading_mode,
        )

    boot_state = recovery_orchestrator.boot()
    if boot_notification_dispatcher is not None:
        boot_notification_dispatcher.dispatch_boot_event(
            app_name=settings.app_name,
            market=settings.trade_market,
            triggered_at=timestamp_provider(),
            cause="process_restart",
            boot_state=boot_state,
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok" if boot_state.trading_ready else "degraded",
            "mode": settings.trading_mode,
            "learning_enabled": settings.learning_enabled,
            "safe_mode": boot_state.safe_mode,
            "hard_stop": boot_state.hard_stop,
            "trading_ready": boot_state.trading_ready,
            "failure_stage": boot_state.failure_stage,
        }

    @app.get("/dashboard/summary")
    def dashboard_summary() -> dict[str, object]:
        summary = dashboard_summary_service.build(
            boot_state=boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            buy_count=0,
            sell_count=0,
            stop_loss_count=0,
            recent_stop_loss_reason=None,
            promotion_ready=promotion_dashboard_facade.is_ready_for_review(),
        )
        if isinstance(summary, dict):
            return summary
        return dashboard_summary_service.to_payload(summary)

    @app.get("/dashboard/promotion")
    def dashboard_promotion() -> dict[str, object]:
        return promotion_dashboard_facade.build_current_response()

    @app.get("/dashboard/promotion/history")
    def dashboard_promotion_history() -> dict[str, object]:
        return promotion_dashboard_facade.build_history_response()

    @app.post("/promotion/review")
    def promotion_review(payload: PromotionReviewPayload) -> dict[str, object]:
        return promotion_review_service.review(
            promotion_review_service.build_command(
                payload.model_dump(),
            ),
        )

    @app.get("/promotion/status")
    def promotion_status() -> dict[str, object]:
        return promotion_state_service.build_status_response()

    @app.get("/promotion/history")
    def promotion_history() -> dict[str, object]:
        return promotion_state_service.build_history_response()

    return app


app = create_app()
