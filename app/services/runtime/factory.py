from __future__ import annotations

from dataclasses import dataclass

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.services.learning.service import LearningService
from app.services.portfolio.sync import PortfolioSyncService
from app.services.recovery.hard_stop import RestartCounter
from app.services.recovery.open_orders import OpenOrderReconciler
from app.services.recovery.orchestrator import InMemoryRestartStore, RecoveryOrchestrator
from app.services.runtime.service import AppRuntimeService


@dataclass(frozen=True)
class RuntimeServices:
    recovery_orchestrator: RecoveryOrchestrator
    runtime_service: AppRuntimeService


def build_runtime_services(
    *,
    app_name: str,
    trading_mode: str,
    upbit_base_url: str,
    upbit_access_key: str,
    upbit_secret_key: str,
    trade_coin: str,
    trade_market: str,
    timestamp_provider,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    learning_service: LearningService | None = None,
    recovery_orchestrator: RecoveryOrchestrator | None = None,
) -> RuntimeServices:
    if recovery_orchestrator is None:
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
            restart_store=InMemoryRestartStore(),
            restart_counter=RestartCounter(threshold=3),
            learning_service=learning_service,
        )

    runtime_service = AppRuntimeService(
        recovery_orchestrator=recovery_orchestrator,
        app_name=app_name,
        market=trade_market,
        timestamp_provider=timestamp_provider,
        boot_notification_dispatcher=boot_notification_dispatcher,
    )

    return RuntimeServices(
        recovery_orchestrator=recovery_orchestrator,
        runtime_service=runtime_service,
    )
