from __future__ import annotations

from fastapi import APIRouter

from app.services.recovery.orchestrator import BootState


def build_health_router(
    *,
    boot_state: BootState,
    trading_mode: str,
    learning_enabled: bool,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok" if boot_state.trading_ready else "degraded",
            "mode": trading_mode,
            "learning_enabled": learning_enabled,
            "safe_mode": boot_state.safe_mode,
            "hard_stop": boot_state.hard_stop,
            "trading_ready": boot_state.trading_ready,
            "failure_stage": boot_state.failure_stage,
        }

    return router
