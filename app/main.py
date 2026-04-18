from __future__ import annotations

from fastapi import FastAPI

from app.core.logging import configure_logging
from app.core.settings import load_settings
from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient
from app.services.portfolio.sync import PortfolioSyncService
from app.services.recovery.orchestrator import (
    InMemoryRestartStore,
    RecoveryOrchestrator,
)
from app.services.recovery.open_orders import OpenOrderReconciler


def create_app(
    recovery_orchestrator: RecoveryOrchestrator | None = None,
) -> FastAPI:
    settings = load_settings()
    configure_logging(settings.learning_log_dir)

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
        )

    boot_state = recovery_orchestrator.boot()

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok" if boot_state.trading_ready else "degraded",
            "mode": settings.trading_mode,
            "learning_enabled": settings.learning_enabled,
            "safe_mode": boot_state.safe_mode,
            "trading_ready": boot_state.trading_ready,
            "failure_stage": boot_state.failure_stage,
        }

    return app


app = create_app()
