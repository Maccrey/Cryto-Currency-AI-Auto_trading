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
from app.services.dashboard.summary import DashboardSummaryService
from app.services.portfolio.sync import PortfolioSyncService
from app.services.promotion.approval import PromotionApprovalFlow
from app.services.promotion.evaluator import PromotionEvaluator
from app.services.promotion.lifecycle import PromotionLifecycleService
from app.services.promotion.runner import PromotionReviewRequest, PromotionRunner
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
    dashboard_summary_service: DashboardSummaryService | None = None,
    promotion_runner: PromotionRunner | None = None,
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
    if promotion_status_store is None:
        promotion_status_store = PromotionStatusStore()

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
        promotion_snapshot = promotion_status_store.get()
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
            promotion_ready=(
                promotion_snapshot is not None
                and promotion_snapshot.evaluation_status == "READY_FOR_REVIEW"
            ),
        )
        if isinstance(summary, dict):
            return summary
        return dashboard_summary_service.to_payload(summary)

    @app.post("/promotion/review")
    def promotion_review(payload: PromotionReviewPayload) -> dict[str, object]:
        result = promotion_runner.run(
            PromotionReviewRequest(
                market=payload.market,
                demo_days=payload.demo_days,
                total_trades=payload.total_trades,
                profit_factor=payload.profit_factor,
                max_drawdown=payload.max_drawdown,
                stoploss_failures=payload.stoploss_failures,
                approval_granted=payload.approval_granted,
                approved_by=payload.approved_by,
                activated_at=payload.activated_at,
            ),
        )
        promotion_status_store.save(
            market=payload.market,
            reviewed_at=payload.activated_at,
            result=result,
        )
        return {
            "status": "ok",
            "evaluation": {
                "status": result.evaluation.status,
                "approved": result.evaluation.approved,
                "rejection_reasons": result.evaluation.rejection_reasons,
            },
            "approval_result": {
                "live_enabled": result.approval_result.live_enabled,
                "safe_mode_entry": result.approval_result.safe_mode_entry,
                "reason_code": result.approval_result.reason_code,
            },
        }

    @app.get("/promotion/status")
    def promotion_status() -> dict[str, object]:
        snapshot = promotion_status_store.get()
        if snapshot is None:
            return {
                "status": "empty",
                "snapshot": None,
            }
        return {
            "status": "ok",
            "snapshot": promotion_status_store.to_payload(snapshot),
        }

    return app


app = create_app()
