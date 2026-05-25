from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter

from app.services.recovery.orchestrator import BootState


def build_health_router(
    *,
    boot_state: BootState,
    boot_state_provider: Callable[[], BootState] | None = None,
    trading_mode: str,
    learning_enabled: bool,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, object]:
        current_boot_state = boot_state_provider() if boot_state_provider is not None else boot_state
        return {
            "status": "ok" if current_boot_state.trading_ready else "degraded",
            "mode": trading_mode,
            "learning_enabled": learning_enabled,
            "safe_mode": current_boot_state.safe_mode,
            "hard_stop": current_boot_state.hard_stop,
            "trading_ready": current_boot_state.trading_ready,
            "failure_stage": current_boot_state.failure_stage,
        }

    return router
