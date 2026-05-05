from __future__ import annotations

from dataclasses import dataclass

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.services.learning.service import LearningService
from app.services.portfolio.sync import PortfolioState
from app.services.portfolio.sync import PortfolioSyncService
from app.services.recovery.hard_stop import RestartCounter
from app.services.recovery.open_orders import OpenOrderReconciler
from pathlib import Path

from app.services.recovery.orchestrator import BootState, FileRestartStateStore, RecoveryOrchestrator
from app.services.runtime.service import AppRuntimeService


@dataclass(frozen=True)
class RuntimeServices:
    recovery_orchestrator: RecoveryOrchestrator
    runtime_service: AppRuntimeService


class StaticRecoveryOrchestrator:
    """Return a fixed boot state for config-only startup modes."""

    def __init__(self, boot_state: BootState) -> None:
        self._boot_state = boot_state

    def boot(self) -> BootState:
        return self._boot_state


def build_runtime_services(
    *,
    app_name: str,
    trading_mode: str,
    upbit_base_url: str,
    upbit_access_key: str,
    upbit_secret_key: str,
    trade_coin: str,
    trade_market: str,
    restart_state_path: Path | None,
    timestamp_provider,
    learning_enabled: bool = True,
    demo_initial_capital: int = 1_000_000,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    learning_service: LearningService | None = None,
    recovery_orchestrator: RecoveryOrchestrator | None = None,
) -> RuntimeServices:
    if recovery_orchestrator is None:
        if trading_mode == "demo":
            recovery_orchestrator = StaticRecoveryOrchestrator(
                BootState(
                    safe_mode=False,
                    hard_stop=False,
                    trading_ready=True,
                    failure_stage=None,
                    portfolio_state=PortfolioState(
                        cash_balance=float(demo_initial_capital),
                        asset_currency=trade_coin,
                        asset_balance=0.0,
                        avg_buy_price=0.0,
                    ),
                    reconcile_result={"open_order_count": 0, "status": "demo_skipped"},
                ),
            )
        elif trading_mode == "live" and (not upbit_access_key or not upbit_secret_key):
            recovery_orchestrator = StaticRecoveryOrchestrator(
                BootState(
                    safe_mode=True,
                    hard_stop=False,
                    trading_ready=False,
                    failure_stage="api_key_missing",
                    portfolio_state=None,
                    reconcile_result=None,
                ),
            )
        else:
            upbit_client = UpbitRestClient(
                base_url=upbit_base_url,
                auth_signer=UpbitAuthSigner(
                    access_key=upbit_access_key,
                    secret_key=upbit_secret_key,
                ),
            )
            recovery_orchestrator = RecoveryOrchestrator(
                app_name=app_name,
                trading_mode=trading_mode,
                portfolio_sync_service=PortfolioSyncService(
                    upbit_client=upbit_client,
                    trade_coin=trade_coin,
                ),
                open_order_reconciler=OpenOrderReconciler(
                    upbit_client=upbit_client,
                    trade_market=trade_market,
                ),
                restart_store=FileRestartStateStore(restart_state_path or Path("./logs/recovery/restart-state.json")),
                restart_counter=RestartCounter(threshold=3),
                learning_service=learning_service,
                market=trade_market,
            )

    runtime_service = AppRuntimeService(
        recovery_orchestrator=recovery_orchestrator,
        app_name=app_name,
        market=trade_market,
        trading_mode=trading_mode,
        learning_enabled=learning_enabled,
        timestamp_provider=timestamp_provider,
        boot_notification_dispatcher=boot_notification_dispatcher,
    )

    return RuntimeServices(
        recovery_orchestrator=recovery_orchestrator,
        runtime_service=runtime_service,
    )
