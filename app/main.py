from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes.decision import build_decision_router
from app.api.routes.dashboard import build_dashboard_router
from app.api.routes.health import build_health_router
from app.api.routes.learning import build_learning_router
from app.api.routes.market import build_market_router
from app.api.routes.position import build_position_router
from app.api.routes.promotion import build_promotion_router
from app.api.routes.settings import build_settings_router
from app.core.logging import configure_logging
from app.core.settings import load_settings
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier
from app.integrations.telegram.notifier import TelegramNotifier
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.factory import build_dashboard_services
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.execution.factory import ExecutionFactory
from app.services.execution.live import UpbitLiveOrderGateway
from app.services.config.env_file import EnvFileService
from app.services.learning.service import LearningService
from app.services.market.store import MarketPriceStore
from app.services.notification.factory import build_notification_services
from app.services.dashboard.overlay import StopLossOverlayService
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.exit import PositionExitService
from app.services.position.risk import PositionRiskService
from app.services.position.store import CurrentPositionStore
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.factory import build_promotion_services
from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.review import PromotionReviewService
from app.services.promotion.runner import PromotionRunner
from app.services.promotion.state import PromotionStateService
from app.services.promotion.status import PromotionStatusStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
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
    position_exit_service: PositionExitService | None = None,
    position_store: CurrentPositionStore | None = None,
    execution_ledger: ExecutionLedger | None = None,
    position_lifecycle_ledger: PositionLifecycleLedger | None = None,
    market_price_store: MarketPriceStore | None = None,
    trade_fill_notifier: TelegramNotifier | None = None,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    restart_notifier: RestartNotifier | None = None,
    hard_stop_notifier: HardStopNotifier | None = None,
    timestamp_provider: Callable[[], str] | None = None,
) -> FastAPI:
    settings = load_settings()
    configure_logging(
        settings.learning_log_dir,
        app_name=settings.app_name,
        trading_mode=settings.trading_mode,
        learning_enabled=settings.learning_enabled,
    )
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
        restart_state_path=settings.restart_state_path,
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
    execution_ledger = execution_ledger or ExecutionLedger()
    position_lifecycle_ledger = position_lifecycle_ledger or PositionLifecycleLedger(
        timestamp_provider=timestamp_provider,
    )

    market_price_store = market_price_store or MarketPriceStore(
        timestamp_provider=timestamp_provider,
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
                min_cash_reserve=float(settings.min_cash_reserve),
                max_spread_bps=float(settings.max_spread_bps),
                max_slippage_bps=float(settings.max_slippage_bps),
                stop_loss_by_signal={
                    "weak": settings.stop_loss_weak,
                    "medium": settings.stop_loss_medium,
                    "strong": settings.stop_loss_strong,
                    "very_strong": settings.stop_loss_very_strong,
                },
            ),
        )

    boot_state = runtime_services.runtime_service.start()
    executor = ExecutionFactory(
        live_order_gateway=UpbitLiveOrderGateway(
            rest_client=UpbitRestClient(
                base_url=settings.upbit_base_url,
                auth_signer=UpbitAuthSigner(
                    access_key=settings.upbit_access_key,
                    secret_key=settings.upbit_secret_key,
                ),
            ),
        ),
        learning_service=learning_service,
    ).create(
        trading_mode=settings.trading_mode,
        safe_mode=boot_state.safe_mode,
        hard_stop=boot_state.hard_stop,
    )
    if trade_execution_service is None:
        trade_execution_service = TradeExecutionService(
            executor=executor,
            market=settings.trade_market,
        )
    if position_store is None:
        position_store = CurrentPositionStore()
    dashboard_services = build_dashboard_services(
        market=settings.trade_market,
        boot_state=boot_state,
        promotion_dashboard_facade=promotion_services.dashboard_facade,
        learning_service=learning_service,
        execution_ledger=execution_ledger,
        position_lifecycle_ledger=position_lifecycle_ledger,
        position_store=position_store,
        market_price_store=market_price_store,
        dashboard_summary_service=dashboard_summary_service,
        dashboard_summary_facade=dashboard_summary_facade,
    )
    position_risk_service = PositionRiskService(
        position_store=position_store,
        hard_stop_monitor=HardStopMonitor(),
        post_entry_validator=PostEntryValidator(),
    )
    if position_exit_service is None:
        position_exit_service = PositionExitService(
            position_store=position_store,
            hard_stop_monitor=HardStopMonitor(),
            post_entry_validator=PostEntryValidator(),
            executor=executor,
            trading_mode=settings.trading_mode,
            learning_service=learning_service,
            telegram_notifier=trade_fill_notifier,
            execution_ledger=execution_ledger,
            position_lifecycle_ledger=position_lifecycle_ledger,
        )
    if post_fill_service is None:
        post_fill_service = PostFillService(
            stop_loss_injector=StopLossInjector(
                stop_loss_by_signal={
                    "weak": settings.stop_loss_weak,
                    "medium": settings.stop_loss_medium,
                    "strong": settings.stop_loss_strong,
                    "very_strong": settings.stop_loss_very_strong,
                },
                validation_window_sec=settings.validation_window_sec,
                min_expected_return_pct=settings.min_expected_return_pct,
            ),
            position_store=position_store,
            telegram_notifier=trade_fill_notifier,
            execution_ledger=execution_ledger,
            position_lifecycle_ledger=position_lifecycle_ledger,
            learning_service=learning_service,
        )

    app = FastAPI(title=settings.app_name)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/settings", status_code=307)

    app.include_router(
        build_health_router(
            boot_state=boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
        ),
    )
    app.include_router(
        build_settings_router(
            env_file_service=EnvFileService(settings.env_file_path),
        ),
    )
    app.include_router(
        build_dashboard_router(
            boot_state=boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
            dashboard_summary_facade=dashboard_services.summary_facade,
            dashboard_market_facade=dashboard_services.market_facade,
            dashboard_executions_facade=dashboard_services.executions_facade,
            dashboard_positions_facade=dashboard_services.positions_facade,
            dashboard_learning_facade=dashboard_services.learning_facade,
            dashboard_recovery_facade=dashboard_services.recovery_facade,
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
            market=settings.trade_market,
            trade_decision_service=trade_decision_service,
            trade_execution_service=trade_execution_service,
            post_fill_service=post_fill_service,
            market_price_store=market_price_store,
        ),
    )
    app.include_router(
        build_position_router(
            position_store=position_store,
            stop_loss_overlay_service=StopLossOverlayService(),
            position_risk_service=position_risk_service,
            position_exit_service=position_exit_service,
            market_price_store=market_price_store,
        ),
    )
    app.include_router(
        build_market_router(
            market=settings.trade_market,
            market_price_store=market_price_store,
        ),
    )
    app.include_router(
        build_learning_router(
            market=settings.trade_market,
            learning_service=learning_service,
        ),
    )
    return app


app = create_app()
