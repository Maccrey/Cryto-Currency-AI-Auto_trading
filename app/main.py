from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI

from app.api.routes.decision import build_decision_router
from app.api.routes.dashboard import build_dashboard_router
from app.api.routes.health import build_health_router
from app.api.routes.promotion import build_promotion_router
from app.core.logging import configure_logging
from app.core.settings import load_settings
from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.factory import build_dashboard_services
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.factory import ExecutionFactory
from app.services.learning.service import LearningService
from app.services.notification.factory import build_notification_services
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.factory import build_promotion_services
from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.review import PromotionReviewService
from app.services.promotion.runner import PromotionRunner
from app.services.promotion.state import PromotionStateService
from app.services.promotion.status import PromotionStatusStore
from app.services.recovery.orchestrator import RecoveryOrchestrator
from app.services.risk.stop_loss import StopLossInjector
from app.services.runtime.factory import build_runtime_services
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.regime.engine import RegimeEngine
from app.services.sizing.engine import SizingEngine
from app.services.trading.decision import TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService


class NoOpLiveOrderGateway:
    def place_order(self, **kwargs) -> dict[str, object]:
        return {"uuid": "blocked", "state": "noop"}


def create_app(
    recovery_orchestrator: RecoveryOrchestrator | None = None,
    promotion_dashboard_service: PromotionDashboardService | None = None,
    dashboard_summary_service: DashboardSummaryService | None = None,
    dashboard_summary_facade: DashboardSummaryFacade | None = None,
    learning_service: LearningService | None = None,
    promotion_runner: PromotionRunner | None = None,
    promotion_dashboard_facade: PromotionDashboardFacade | None = None,
    promotion_review_service: PromotionReviewService | None = None,
    promotion_state_service: PromotionStateService | None = None,
    promotion_history_store: PromotionHistoryStore | None = None,
    promotion_status_store: PromotionStatusStore | None = None,
    trade_decision_service: TradeDecisionService | None = None,
    trade_execution_service: TradeExecutionService | None = None,
    post_fill_service: PostFillService | None = None,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    restart_notifier: RestartNotifier | None = None,
    hard_stop_notifier: HardStopNotifier | None = None,
    timestamp_provider: Callable[[], str] | None = None,
) -> FastAPI:
    settings = load_settings()
    configure_logging(settings.learning_log_dir)
    timestamp_provider = timestamp_provider or (lambda: datetime.now().astimezone().isoformat())

    if learning_service is None:
        learning_service = LearningService(log_dir=settings.learning_log_dir)

    if promotion_dashboard_service is None:
        promotion_dashboard_service = PromotionDashboardService()

    notification_services = build_notification_services(
        boot_notification_dispatcher=boot_notification_dispatcher,
        restart_notifier=restart_notifier,
        hard_stop_notifier=hard_stop_notifier,
    )

    runtime_services = build_runtime_services(
        app_name=settings.app_name,
        trading_mode=settings.trading_mode,
        upbit_base_url=settings.upbit_base_url,
        upbit_access_key=settings.upbit_access_key,
        upbit_secret_key=settings.upbit_secret_key,
        trade_coin=settings.trade_coin,
        trade_market=settings.trade_market,
        timestamp_provider=timestamp_provider,
        boot_notification_dispatcher=notification_services.boot_notification_dispatcher,
        learning_service=learning_service,
        recovery_orchestrator=recovery_orchestrator,
    )

    promotion_services = build_promotion_services(
        trading_mode=settings.trading_mode,
        learning_service=learning_service,
        promotion_runner=promotion_runner,
        promotion_dashboard_service=promotion_dashboard_service,
        promotion_review_service=promotion_review_service,
        promotion_dashboard_facade=promotion_dashboard_facade,
        promotion_state_service=promotion_state_service,
        promotion_history_store=promotion_history_store,
        promotion_status_store=promotion_status_store,
    )

    dashboard_services = build_dashboard_services(
        promotion_dashboard_facade=promotion_services.dashboard_facade,
        dashboard_summary_service=dashboard_summary_service,
        dashboard_summary_facade=dashboard_summary_facade,
    )
    if trade_decision_service is None:
        trade_decision_service = TradeDecisionService(
            feature_calculator=MarketFeatureCalculator(),
            signal_engine=SignalEngine(
                learning_service=learning_service,
                trading_mode=settings.trading_mode,
            ),
            regime_engine=RegimeEngine(),
            sizing_engine=SizingEngine(
                min_cash_reserve=100000.0,
                max_spread_bps=15.0,
                max_slippage_bps=20.0,
            ),
        )

    boot_state = runtime_services.runtime_service.start()
    if trade_execution_service is None:
        trade_execution_service = TradeExecutionService(
            executor=ExecutionFactory(
                live_order_gateway=NoOpLiveOrderGateway(),
            ).create(
                trading_mode=settings.trading_mode,
                safe_mode=boot_state.safe_mode,
                hard_stop=boot_state.hard_stop,
            ),
            market=settings.trade_market,
        )
    if post_fill_service is None:
        post_fill_service = PostFillService(
            stop_loss_injector=StopLossInjector(
                stop_loss_by_signal={
                    "weak": 0.008,
                    "medium": 0.012,
                    "strong": 0.018,
                    "very_strong": 0.022,
                },
                validation_window_sec=180,
                min_expected_return_pct=0.004,
            ),
        )

    app = FastAPI(title=settings.app_name)
    app.include_router(
        build_health_router(
            boot_state=boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
        ),
    )
    app.include_router(
        build_dashboard_router(
            boot_state=boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
            dashboard_summary_facade=dashboard_services.summary_facade,
            promotion_dashboard_facade=promotion_services.dashboard_facade,
        ),
    )
    app.include_router(
        build_promotion_router(
            promotion_review_service=promotion_services.review_service,
            promotion_state_service=promotion_services.state_service,
        ),
    )
    app.include_router(
        build_decision_router(
            trade_decision_service=trade_decision_service,
            trade_execution_service=trade_execution_service,
            post_fill_service=post_fill_service,
        ),
    )
    return app


app = create_app()
