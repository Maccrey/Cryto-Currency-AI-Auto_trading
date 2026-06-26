from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes.decision import build_decision_router
from app.api.routes.dashboard import build_dashboard_router
from app.api.routes.health import build_health_router
from app.api.routes.learning import build_learning_router
from app.api.routes.market import build_market_router
from app.api.routes.position import build_position_router
from app.api.routes.promotion import build_promotion_router
from app.api.routes.rules import build_rules_router
from app.api.routes.settings import build_settings_router
from app.core.logging import configure_logging
from app.core.network import build_browser_urls
from app.core.settings import load_settings
from app.core.trading_profile import get_trading_profile, learning_log_dir_for_coin_profile
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.gateway import TelegramHttpGateway
from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier
from app.integrations.telegram.notifier import TelegramNotifier
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.factory import build_dashboard_services
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.ledger import ExecutionLedger
from app.services.execution.demo import FillResult
from app.services.execution.factory import ExecutionFactory
from app.services.execution.live import UpbitLiveOrderGateway
from app.services.execution.rules import UpbitOrderRules
from app.services.config.env_file import EnvFileService
from app.services.learning.service import LearningService
from app.services.learning.jsonl import iter_jsonl_objects
from app.services.learning.model_readiness import ModelTrainingReadinessService
from app.services.learning.reset import LearningDataResetService
from app.services.market.bootstrap import HistoricalMarketBootstrapService, UpbitHistoricalCandleProvider
from app.services.market.store import MarketPriceStore
from app.services.market.context import (
    ExternalMarketContextConfig,
    ExternalMarketContextService,
    HttpExternalMarketContextProvider,
    PublicWebExternalMarketContextProvider,
)
from app.services.market.upbit_ticker import UpbitTickerPriceProvider
from app.services.notification.factory import build_notification_services
from app.services.portfolio.sync import PortfolioState, PortfolioSyncService
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
from app.services.rules.automation import AutoRuleUpdateService
from app.services.rules.review import RuleReviewConfig, RuleReviewService
from app.services.runtime.factory import build_runtime_services
from app.services.runtime.uptime import TradingUptimeStore
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.regime.engine import RegimeEngine
from app.services.sizing.engine import BuySizingPolicy, SellSizingPolicy, SizingEngine
from app.services.trading.auto import AutoTradingConfig, AutoTradingService
from app.services.trading.decision import TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService
from app.services.reporting.daily_report import DailyReportService


logger = logging.getLogger(__name__)


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
    env_file_service = EnvFileService(settings.env_file_path)
    trading_profile = get_trading_profile(settings.trading_profile)
    profile_learning_log_dir = learning_log_dir_for_coin_profile(
        settings.learning_log_dir,
        settings.trading_profile,
        settings.trade_coin,
    )
    configure_logging(
        profile_learning_log_dir,
        app_name=settings.app_name,
        trading_mode=settings.trading_mode,
        learning_enabled=settings.learning_enabled,
    )
    timestamp_provider = timestamp_provider or (lambda: datetime.now().astimezone().isoformat())
    browser_urls = build_browser_urls(
        host=os.getenv("TRADING_HOST", settings.dashboard_host),
        port=int(os.getenv("TRADING_PORT", str(settings.dashboard_port))),
    )
    order_rules = UpbitOrderRules(
        min_order_amount_krw=float(settings.min_order_amount_krw),
    )

    if learning_service is None:
        learning_service = LearningService(
            log_dir=profile_learning_log_dir,
            trading_profile=settings.trading_profile,
        )

    if promotion_dashboard_service is None:
        promotion_dashboard_service = PromotionDashboardService()

    telegram_gateway = None
    if settings.telegram_bot_token and settings.telegram_chat_id:

        def current_server_name() -> str:
            return env_file_service.server_name(fallback=settings.server_name)

        telegram_gateway = TelegramHttpGateway(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            server_name=settings.server_name,
            server_name_provider=current_server_name,
        )
        if trade_fill_notifier is None:
            trade_fill_notifier = TelegramNotifier(
                gateway=telegram_gateway,
                server_name_provider=current_server_name,
            )
        if restart_notifier is None and settings.restart_notify:
            restart_notifier = RestartNotifier(gateway=telegram_gateway)
        if hard_stop_notifier is None:
            hard_stop_notifier = HardStopNotifier(gateway=telegram_gateway)
        if boot_notification_dispatcher is None and settings.restart_notify:
            boot_notification_dispatcher = BootNotificationDispatcher(
                restart_notifier=restart_notifier,
                hard_stop_notifier=hard_stop_notifier,
                dashboard_url=browser_urls["dashboard_url"],
                settings_url=browser_urls["settings_url"],
                dedupe_store_path=settings.restart_state_path.parent / "boot-notification-state.json",
            )

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
        learning_enabled=settings.learning_enabled,
        demo_initial_capital=settings.demo_initial_capital,
        boot_notification_dispatcher=notification_services.boot_notification_dispatcher,
        learning_service=learning_service,
        recovery_orchestrator=recovery_orchestrator,
        dispatch_boot_notification_on_start=False,
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
    runtime_state_dir = profile_learning_log_dir / "runtime-state"
    if execution_ledger is None:
        execution_ledger = ExecutionLedger(
            storage_path=(
                runtime_state_dir / "execution-ledger.json"
                if settings.trading_mode == "demo" and "PYTEST_CURRENT_TEST" not in os.environ
                else None
            ),
        )
    if (
        settings.trading_mode != "demo"
        and "PYTEST_CURRENT_TEST" not in os.environ
        and not execution_ledger.list_records()
    ):
        _seed_execution_ledger_from_learning_log(
            log_path=profile_learning_log_dir / "learning.jsonl",
            execution_ledger=execution_ledger,
            limit=200,
            initial_cash=float(settings.demo_initial_capital),
        )
    position_lifecycle_ledger = position_lifecycle_ledger or PositionLifecycleLedger(
        timestamp_provider=timestamp_provider,
    )

    market_price_store = market_price_store or MarketPriceStore(
        timestamp_provider=timestamp_provider,
    )
    external_context_service = ExternalMarketContextService(
        config=ExternalMarketContextConfig(
            enabled=settings.external_context_enabled,
            onchain_source=settings.onchain_context_source,
            onchain_url=settings.onchain_context_url,
            onchain_state=settings.onchain_state,
            onchain_active_addresses_change_pct=settings.onchain_active_addresses_change_pct,
            onchain_exchange_netflow_state=settings.onchain_exchange_netflow_state,
            etf_source=settings.etf_context_source,
            etf_url=settings.etf_context_url,
            etf_state=settings.etf_state,
            etf_flow_usd=settings.etf_flow_usd,
        ),
        provider=(
            HttpExternalMarketContextProvider(
                onchain_url=settings.onchain_context_url,
                etf_url=settings.etf_context_url,
                cache_ttl_sec=settings.external_context_cache_ttl_sec,
            )
            if settings.onchain_context_url or settings.etf_context_url
            else PublicWebExternalMarketContextProvider(
                cache_ttl_sec=settings.external_context_cache_ttl_sec,
            )
        ),
    )
    if trade_decision_service is None:
        trade_decision_service = TradeDecisionService(
            feature_calculator=MarketFeatureCalculator(),
            signal_engine=SignalEngine(
                learning_service=learning_service,
                trading_mode=settings.trading_mode,
                market=settings.trade_market,
            ),
            regime_engine=RegimeEngine(),
            sizing_engine=SizingEngine(
                min_cash_reserve=float(settings.min_cash_reserve),
                max_spread_bps=float(settings.max_spread_bps),
                max_slippage_bps=float(settings.max_slippage_bps),
                max_stop_loss_risk_amount=float(settings.max_daily_loss) * 0.25,
                capital_risk_pct=float(settings.capital_risk_pct),
                trading_fee_rate=float(settings.trading_fee_rate),
                order_rules=order_rules,
                min_net_edge_pct=float(settings.profile_min_net_edge_pct),
                buy_policy=BuySizingPolicy(
                    {
                        "weak": settings.buy_ratio_weak,
                        "medium": settings.buy_ratio_medium,
                        "strong": settings.buy_ratio_strong,
                        "very_strong": settings.buy_ratio_very_strong,
                    },
                ),
                sell_policy=SellSizingPolicy(
                    {
                        "weak": settings.sell_ratio_weak,
                        "medium": settings.sell_ratio_medium,
                        "strong": settings.sell_ratio_strong,
                        "very_strong": settings.sell_ratio_very_strong,
                    },
                ),
                stop_loss_by_signal=trading_profile.stop_loss_by_signal(),
            ),
        )

    boot_state = runtime_services.runtime_service.start()
    runtime_boot_state = {"value": boot_state}

    def current_boot_state():
        return runtime_boot_state["value"]

    def current_boot_portfolio_state() -> PortfolioState | None:
        return getattr(current_boot_state(), "portfolio_state", None)

    def set_boot_portfolio_state(portfolio: PortfolioState) -> None:
        current_state = current_boot_state()
        try:
            runtime_boot_state["value"] = replace(current_state, portfolio_state=portfolio)
        except TypeError:
            setattr(current_state, "portfolio_state", portfolio)
            runtime_boot_state["value"] = current_state

    def demo_initial_portfolio() -> PortfolioState:
        current_portfolio = current_boot_portfolio_state()
        return PortfolioState(
            cash_balance=float(env_file_service.demo_initial_capital(fallback=settings.demo_initial_capital)),
            asset_currency=(
                current_portfolio.asset_currency
                if current_portfolio is not None
                else settings.trade_coin
            ),
            asset_balance=0.0,
            avg_buy_price=0.0,
        )

    demo_portfolio_state = None
    notification_boot_state = current_boot_state()
    boot_portfolio_state = current_boot_portfolio_state()
    if (
        settings.trading_mode == "demo"
        and boot_portfolio_state is not None
        and execution_ledger.list_records()
    ):
        demo_portfolio_state = execution_ledger.portfolio_state(
            initial_cash=float(env_file_service.demo_initial_capital(fallback=settings.demo_initial_capital)),
            asset_currency=boot_portfolio_state.asset_currency,
        )
        current_state = current_boot_state()
        try:
            notification_boot_state = replace(current_state, portfolio_state=demo_portfolio_state)
        except TypeError:
            notification_boot_state = SimpleNamespace(
                safe_mode=getattr(current_state, "safe_mode", False),
                hard_stop=getattr(current_state, "hard_stop", False),
                trading_ready=getattr(current_state, "trading_ready", False),
                failure_stage=getattr(current_state, "failure_stage", None),
                portfolio_state=demo_portfolio_state,
                reconcile_result=getattr(current_state, "reconcile_result", None),
            )
    runtime_services.runtime_service.dispatch_boot_notification(boot_state=notification_boot_state)
    live_rest_client = UpbitRestClient(
        base_url=settings.upbit_base_url,
        auth_signer=UpbitAuthSigner(
            access_key=settings.upbit_access_key,
            secret_key=settings.upbit_secret_key,
        ),
    )
    live_order_gateway = UpbitLiveOrderGateway(rest_client=live_rest_client)
    live_portfolio_sync_service = PortfolioSyncService(
        upbit_client=live_rest_client,
        trade_coin=settings.trade_coin,
    )
    executor = ExecutionFactory(
        live_order_gateway=live_order_gateway,
        learning_service=learning_service,
        fee_rate=float(settings.trading_fee_rate),
        order_rules=order_rules,
    ).create(
        trading_mode=settings.trading_mode,
        safe_mode=boot_state.safe_mode,
        hard_stop=boot_state.hard_stop,
    )
    if trade_execution_service is None:
        trade_execution_service = TradeExecutionService(
            executor=executor,
            market=settings.trade_market,
            order_rules=order_rules,
        )
    if position_store is None:
        position_store = CurrentPositionStore(
            storage_path=(
                runtime_state_dir / "current-position.json"
                if settings.trading_mode == "demo" and "PYTEST_CURRENT_TEST" not in os.environ
                else None
            ),
        )
    current_price_provider = UpbitTickerPriceProvider(
        base_url=settings.upbit_base_url,
    )
    market_history_bootstrap_result: dict[str, object] = {
        "status": "skipped",
        "reason": "pytest",
    }
    if "PYTEST_CURRENT_TEST" not in os.environ:
        historical_candle_provider = UpbitHistoricalCandleProvider(
            base_url=settings.upbit_base_url,
        )
        try:
            market_history_bootstrap_result = HistoricalMarketBootstrapService(
                market=settings.trade_market,
                trading_mode=settings.trading_mode,
                candle_provider=historical_candle_provider,
                market_price_store=market_price_store,
                learning_service=learning_service,
                observation_path=profile_learning_log_dir / "market-observations.jsonl",
            ).bootstrap()
            logger.info(
                "market_history_bootstrap_completed",
                extra={"event": market_history_bootstrap_result},
            )
        except Exception as exc:
            market_history_bootstrap_result = {
                "status": "failed",
                "source": "upbit_3d_bootstrap",
                "message": str(exc),
            }
            logger.warning(
                "market_history_bootstrap_failed",
                extra={"event": market_history_bootstrap_result},
                exc_info=True,
            )
        finally:
            historical_candle_provider.close()
    dashboard_services = build_dashboard_services(
        market=settings.trade_market,
        boot_state=boot_state,
        promotion_dashboard_facade=promotion_services.dashboard_facade,
        learning_service=learning_service,
        execution_ledger=execution_ledger,
        position_lifecycle_ledger=position_lifecycle_ledger,
        position_store=position_store,
        market_price_store=market_price_store,
        current_price_provider=current_price_provider,
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
            initial_portfolio_state=boot_portfolio_state,
            initial_portfolio_state_provider=current_boot_portfolio_state,
            position_lifecycle_ledger=position_lifecycle_ledger,
            order_rules=order_rules,
            trading_fee_rate=float(settings.trading_fee_rate),
        )
    if post_fill_service is None:
        post_fill_service = PostFillService(
            stop_loss_injector=StopLossInjector(
                stop_loss_by_signal=trading_profile.stop_loss_by_signal(),
                validation_window_sec=settings.validation_window_sec,
                min_expected_return_pct=settings.min_expected_return_pct,
            ),
            position_store=position_store,
            telegram_notifier=trade_fill_notifier,
            execution_ledger=execution_ledger,
            initial_portfolio_state=boot_portfolio_state,
            initial_portfolio_state_provider=current_boot_portfolio_state,
            position_lifecycle_ledger=position_lifecycle_ledger,
            learning_service=learning_service,
        )

    app = FastAPI(title=settings.app_name)
    auto_trading_service = AutoTradingService(
        market=settings.trade_market,
        trading_mode=settings.trading_mode,
        boot_state=boot_state,
        price_provider=current_price_provider,
        market_price_store=market_price_store,
        position_store=position_store,
        trade_decision_service=trade_decision_service,
        trade_execution_service=trade_execution_service,
        post_fill_service=post_fill_service,
        position_exit_service=position_exit_service,
        learning_service=learning_service,
        config=AutoTradingConfig(
            enabled=settings.auto_trading_enabled,
            live_enabled=settings.auto_trading_live_enabled,
            interval_sec=settings.auto_trading_interval_sec,
            min_history=settings.auto_trading_min_history,
            initial_observation_warmup_seconds=settings.auto_trading_initial_warmup_seconds,
            initial_observation_min_samples=settings.auto_trading_initial_warmup_min_samples,
            trading_profile=settings.trading_profile,
            spread_bps=trading_profile.spread_bps,
            slippage_bps=trading_profile.slippage_bps,
            trading_fee_rate=float(settings.trading_fee_rate),
            no_trade_adaptive_enabled=settings.no_trade_adaptive_enabled,
            no_trade_relax_after_cycles=settings.no_trade_relax_after_cycles,
            no_trade_relax_min_score=settings.no_trade_relax_min_score,
            reentry_block_seconds=settings.reentry_block_seconds,
            sideways_risk_guard_enabled=settings.sideways_risk_guard_enabled,
            sideways_price_range_pct=settings.sideways_price_range_pct,
            sideways_traded_value_range_pct=settings.sideways_traded_value_range_pct,
            sideways_max_avg_abs_return_pct=settings.sideways_max_avg_abs_return_pct,
            sideways_scale_in_min_discount_pct=settings.sideways_scale_in_min_discount_pct,
            market_shock_guard_enabled=settings.market_shock_guard_enabled,
            market_crash_change_pct=settings.market_crash_change_pct,
            market_surge_change_pct=settings.market_surge_change_pct,
            market_recovery_change_pct=settings.market_recovery_change_pct,
            market_recovery_confirmation_ticks=settings.market_recovery_confirmation_ticks,
            market_shock_alert_cooldown_sec=settings.market_shock_alert_cooldown_sec,
        ),
        external_context_provider=external_context_service,
        demo_portfolio_state=demo_portfolio_state,
        live_portfolio_sync_service=live_portfolio_sync_service,
        telegram_notifier=trade_fill_notifier,
        uptime_store=TradingUptimeStore(path=runtime_state_dir / "trading-uptime.json"),
        execution_ledger=execution_ledger,
    )
    app.state.auto_trading_service = auto_trading_service
    app.state.market_history_bootstrap_result = market_history_bootstrap_result

    def apply_saved_demo_initial_capital(*, force_reset: bool = False) -> dict[str, object]:
        if settings.trading_mode != "demo":
            return {
                "status": "skipped",
                "applied": False,
                "reason": "not_demo_mode",
            }
        if not force_reset and (
            auto_trading_service.is_running()
            or position_store.get() is not None
            or bool(execution_ledger.list_records())
        ):
            return {
                "status": "deferred",
                "applied": False,
                "reason": "demo_runtime_data_exists",
                "message": "저장된 데모 시작 투자금은 데모 트레이딩 데이터 리셋 후 적용됩니다.",
            }
        portfolio = demo_initial_portfolio()
        set_boot_portfolio_state(portfolio)
        result = auto_trading_service.set_demo_portfolio_baseline(portfolio)
        return {
            "status": "applied" if result.get("applied") else "skipped",
            "applied": bool(result.get("applied")),
            "cash_balance": result.get("cash_balance"),
            "asset_currency": result.get("asset_currency"),
            "asset_balance": result.get("asset_balance"),
        }
    rule_review_service = RuleReviewService(
        market=settings.trade_market,
        trade_coin=settings.trade_coin,
        trading_mode=settings.trading_mode,
        learning_log_dir=profile_learning_log_dir,
        config=RuleReviewConfig(
            enabled=settings.rule_review_enabled,
            window_days=settings.rule_review_window_days,
            min_trades=settings.rule_review_min_trades,
            min_stoplosses=settings.rule_review_min_stoplosses,
            max_params_per_run=settings.rule_change_max_params_per_run,
            apply_target=settings.rule_change_apply_target,
            require_manual_approval=settings.rule_change_require_manual_approval,
            auto_update_enabled=settings.auto_rule_update_enabled,
            auto_update_min_learning_completion_rate=settings.auto_rule_update_min_learning_completion_rate,
            auto_update_win_rate_skip_threshold=settings.auto_rule_update_win_rate_skip_threshold,
        ),
        telegram_gateway=telegram_gateway,
        demo_rule_reset_callback=auto_trading_service.reset_demo_rule_variants,
    )
    auto_trading_service._auto_rule_update_service = AutoRuleUpdateService(
        readiness_service=ModelTrainingReadinessService(log_dir=profile_learning_log_dir),
        rule_review_service=rule_review_service,
        fixture_path=Path("fixtures/replay_ticks.json"),
        no_trade_trigger_hours=settings.auto_rule_update_no_trade_hours,
    )

    @app.on_event("shutdown")
    async def stop_auto_trading_service() -> None:
        await auto_trading_service.stop()
        daily_report_service.stop()

    # ── 일일 리포트 서비스 설정 ────────────────────────────────────────────
    def _get_demo_portfolio_state():
        """Auto trading service에서 현재 데모 포트폴리오 상태를 반환합니다."""
        try:
            return auto_trading_service.current_demo_portfolio_state()
        except Exception:
            return None

    daily_report_service = DailyReportService(
        execution_ledger=execution_ledger,
        telegram_gateway=telegram_gateway,
        market=settings.trade_market,
        trading_mode=settings.trading_mode,
        report_hour_kst=8,
        portfolio_state_provider=_get_demo_portfolio_state if settings.trading_mode == "demo" else None,
    )

    @app.on_event("startup")
    async def start_daily_report_scheduler() -> None:
        if telegram_gateway is not None:
            daily_report_service.start()
            logger.info(
                "daily_report_scheduler_registered",
                extra={"report_hour_kst": 8, "market": settings.trade_market},
            )
        else:
            logger.info("daily_report_scheduler_skipped_no_telegram")
    # ───────────────────────────────────────────────────────────────
    def _send_telegram_lifecycle_message(lines: list[str]) -> dict[str, object]:
        return {
            "status": "disabled",
            "sent": False,
            "message": "체결이 아닌 자동 텔레그램 알림은 비활성화되어 있습니다.",
        }

    def _build_trading_response_message(base_message: str, notification: dict[str, object]) -> str:
        if notification.get("status") == "failed":
            return f"{base_message} {notification.get('message')}"
        if notification.get("status") == "not_configured":
            return f"{base_message} {notification.get('message')}"
        return base_message

    def start_trading_service() -> dict[str, object]:
        if auto_trading_service.is_running():
            telegram_notification = _send_telegram_lifecycle_message(
                [
                    "트레이딩 서버가 이미 실행 중입니다.",
                    f"거래 시장은 {settings.trade_market}이고 거래 모드는 {settings.trading_mode}입니다.",
                    f"대시보드는 브라우저에서 {browser_urls['dashboard_url']} 주소로 열 수 있습니다.",
                ],
            )
            message = _build_trading_response_message("트레이딩 서버가 이미 실행 중입니다.", telegram_notification)
            return {
                "status": "already_running",
                "started": True,
                "running": True,
                "telegram_notification": telegram_notification,
                "message": message,
            }
        apply_saved_demo_initial_capital()
        if not auto_trading_service.should_run():
            return {
                "status": "not_ready",
                "started": False,
                "running": False,
                "message": "트레이딩 서버를 시작할 수 없습니다. 안전 모드, HARD_STOP, live 실행 허용 설정을 확인하세요.",
            }
        auto_trading_service.start()
        telegram_notification = _send_telegram_lifecycle_message(
            [
                "자동매매 루프가 시작되었습니다.",
                f"거래 시장은 {settings.trade_market}이고 거래 모드는 {settings.trading_mode}입니다.",
                f"대시보드는 브라우저에서 {browser_urls['dashboard_url']} 주소로 열 수 있습니다.",
                f"설정 화면은 브라우저에서 {browser_urls['settings_url']} 주소로 열 수 있습니다.",
            ],
        )
        message = _build_trading_response_message("자동매매 루프가 시작되었습니다.", telegram_notification)
        return {
            "status": "started",
            "started": True,
            "running": True,
            "telegram_notification": telegram_notification,
            "message": message,
        }

    def trading_status_service() -> dict[str, object]:
        running = auto_trading_service.is_running()
        startable = auto_trading_service.should_run()
        if running:
            message = "자동매매 루프가 실행 중입니다."
        elif startable:
            message = "자동매매 루프를 시작할 수 있습니다."
        else:
            message = "자동매매 루프를 시작할 수 없습니다. 안전 모드, HARD_STOP, live 실행 허용 설정을 확인하세요."
        return {
            "status": "running" if running else "stopped",
            "running": running,
            "startable": startable,
            "started_at": (
                None
                if not running or auto_trading_service.started_at() is None
                else auto_trading_service.started_at().isoformat()
            ),
            "uptime_sec": auto_trading_service.uptime_sec() if running else None,
            "last_cycle": auto_trading_service.last_cycle(),
            "message": message,
        }

    async def stop_trading_service() -> dict[str, object]:
        if not auto_trading_service.is_running():
            return {
                "status": "already_stopped",
                "stopped": True,
                "running": False,
                "message": "자동매매 루프가 이미 중지되어 있습니다.",
            }
        await auto_trading_service.stop()
        telegram_notification = _send_telegram_lifecycle_message(
            [
                "자동매매 루프가 중지되었습니다.",
                f"거래 시장은 {settings.trade_market}이고 거래 모드는 {settings.trading_mode}입니다.",
                "설정 화면은 계속 열려 있으며 시작 버튼으로 다시 실행할 수 있습니다.",
            ],
        )
        message = _build_trading_response_message("자동매매 루프가 중지되었습니다.", telegram_notification)
        return {
            "status": "stopped",
            "stopped": True,
            "running": False,
            "telegram_notification": telegram_notification,
            "message": message,
        }

    def reset_demo_trading_data_service() -> dict[str, object]:
        if settings.trading_mode != "demo":
            return {
                "status": "blocked",
                "reset": False,
                "message": "데모 트레이딩 데이터 리셋은 demo 모드에서만 사용할 수 있습니다.",
            }
        execution_ledger.clear()
        position_lifecycle_ledger.clear()
        position_store.clear()
        portfolio = demo_initial_portfolio()
        set_boot_portfolio_state(portfolio)
        demo_result = auto_trading_service.reset_demo_portfolio(portfolio)
        return {
            "status": "reset" if demo_result.get("reset") else "skipped",
            "reset": bool(demo_result.get("reset")),
            "message": "데모 트레이딩 데이터가 리셋되었습니다.",
            **demo_result,
        }

    learning_data_reset_service = LearningDataResetService(log_dir=profile_learning_log_dir)

    def purge_runtime_data_service() -> dict[str, object]:
        deleted_paths: list[str] = []
        learning_result = learning_data_reset_service.delete()
        if learning_service is not None:
            learning_service.clear_recent_events()
        execution_ledger.clear()
        position_lifecycle_ledger.clear()
        position_store.clear()
        market_price_store.clear(settings.trade_market)
        market_runtime_result = auto_trading_service.reset_runtime_market_data()
        portfolio = demo_initial_portfolio()
        set_boot_portfolio_state(portfolio)
        demo_result = auto_trading_service.reset_demo_portfolio(portfolio)
        for path in [
            runtime_state_dir / "execution-ledger.json",
            runtime_state_dir / "current-position.json",
            runtime_state_dir / "trading-uptime.json",
            profile_learning_log_dir / "market-observations.jsonl",
        ]:
            if path.exists():
                path.unlink()
                deleted_paths.append(str(path))
        return {
            "status": "reset",
            "reset": True,
            "message": "학습 로그와 데모 매매 데이터가 보관 없이 완전 삭제되었습니다.",
            "learning_log_path": learning_result.log_path,
            "archive_path": None,
            "deleted_paths": deleted_paths,
            "market_runtime": market_runtime_result,
            "demo_trading": demo_result,
        }

    def telegram_test_service() -> dict[str, object]:
        if telegram_gateway is None:
            return {
                "status": "not_configured",
                "sent": False,
                "message": "텔레그램 봇 토큰과 채팅 ID가 설정되어 있지 않습니다. 저장 후 서버를 재시작하세요.",
            }
        try:
            telegram_gateway.send_message(
                "\n".join(
                    [
                        "텔레그램 테스트 메시지입니다.",
                        f"거래 시장: {settings.trade_market}",
                        f"거래 모드: {settings.trading_mode}",
                    ],
                ),
            )
        except Exception as exc:
            return {
                "status": "failed",
                "sent": False,
                "message": f"텔레그램 테스트 메시지 전송 실패: {exc}",
            }
        return {
            "status": "sent",
            "sent": True,
            "message": "텔레그램 테스트 메시지를 전송했습니다.",
        }

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/settings", status_code=307)

    app.include_router(
        build_health_router(
            boot_state=boot_state,
            boot_state_provider=current_boot_state,
            trading_mode=settings.trading_mode,
            learning_enabled=settings.learning_enabled,
        ),
    )
    app.include_router(
        build_settings_router(
            env_file_service=env_file_service,
            learning_data_reset_service=learning_data_reset_service,
            learning_service=learning_service,
            start_trading_service=start_trading_service,
            stop_trading_service=stop_trading_service,
            trading_status_service=trading_status_service,
            reset_demo_trading_data_service=reset_demo_trading_data_service,
            purge_runtime_data_service=purge_runtime_data_service,
            telegram_test_service=telegram_test_service,
            after_save_service=apply_saved_demo_initial_capital,
        ),
    )
    app.include_router(
        build_dashboard_router(
            boot_state=boot_state,
            boot_state_provider=current_boot_state,
            trading_mode=settings.trading_mode,
            trading_profile=settings.trading_profile,
            trading_profile_label=trading_profile.label,
            learning_enabled=settings.learning_enabled,
            dashboard_summary_facade=dashboard_services.summary_facade,
            dashboard_market_facade=dashboard_services.market_facade,
            dashboard_executions_facade=dashboard_services.executions_facade,
            dashboard_positions_facade=dashboard_services.positions_facade,
            dashboard_learning_facade=dashboard_services.learning_facade,
            dashboard_recovery_facade=dashboard_services.recovery_facade,
            promotion_dashboard_facade=promotion_services.dashboard_facade,
            external_context_provider=lambda force=False: external_context_service.snapshot(
                market=settings.trade_market,
                trade_coin=settings.trade_coin,
                force=force,
            ),
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
            trade_coin=settings.trade_coin,
            learning_service=learning_service,
            learning_log_dir=profile_learning_log_dir,
        ),
    )
    app.include_router(build_rules_router(rule_review_service=rule_review_service, learning_service=learning_service))
    return app


def _seed_execution_ledger_from_learning_log(
    *,
    log_path: Path,
    execution_ledger: ExecutionLedger,
    limit: int,
    initial_cash: float,
) -> None:
    if not log_path.exists() or limit <= 0:
        return
    cash_balance = initial_cash
    asset_balance = 0.0
    solvent_records: deque[tuple[FillResult, str | None]] = deque(maxlen=limit)
    for row in iter_jsonl_objects(log_path):
        if row.get("event_name") != "fill_result":
            continue
        payload = row.get("payload") or {}
        try:
            fill = FillResult(
                market=str(row.get("market") or "unknown"),
                side=str(payload.get("side")),
                filled_price=float(payload.get("filled_price", 0.0)),
                filled_quantity=float(payload.get("filled_quantity", 0.0)),
                fee=float(payload.get("fee", 0.0)),
                status=str(payload.get("status") or "filled"),
                mode=str(row.get("mode") or "demo"),
                is_virtual=str(row.get("mode") or "demo") == "demo",
                is_stop_loss=bool(payload.get("is_stop_loss")),
            )
        except (TypeError, ValueError):
            continue
        if fill.status != "filled":
            continue
        gross_amount = fill.filled_price * fill.filled_quantity
        if fill.side == "buy":
            if gross_amount + fill.fee > cash_balance:
                continue
            cash_balance -= gross_amount + fill.fee
            asset_balance += fill.filled_quantity
            solvent_records.append((fill, payload.get("reason_code")))
            continue
        if fill.side == "sell":
            sell_quantity = min(asset_balance, fill.filled_quantity)
            if sell_quantity <= 0:
                continue
            cash_balance += (fill.filled_price * sell_quantity) - fill.fee
            asset_balance = round(asset_balance - sell_quantity, 8)
            solvent_records.append((fill, payload.get("reason_code")))
    for fill, reason_code in solvent_records:
        execution_ledger.record_fill(fill, reason_code=None if reason_code is None else str(reason_code))


app = create_app()
