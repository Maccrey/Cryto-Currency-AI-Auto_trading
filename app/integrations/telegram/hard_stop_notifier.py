from __future__ import annotations

import logging
from typing import Any

from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


class HardStopNotifier:
    """Send HARD_STOP operational alerts through Telegram."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_hard_stop(
        self,
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        boot_state: BootState,
    ) -> None:
        try:
            self._gateway.send_message(
                self._build_message(
                    app_name=app_name,
                    market=market,
                    triggered_at=triggered_at,
                    boot_state=boot_state,
                ),
            )
        except Exception:
            logger.exception(
                "telegram_hard_stop_notification_failed",
                extra={"app_name": app_name, "market": market},
            )

    @staticmethod
    def _build_message(
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        boot_state: BootState,
    ) -> str:
        reconcile_result = boot_state.reconcile_result or {}
        restart_count = reconcile_result.get("restart_count", "unknown")
        blocked_reason = reconcile_result.get("blocked_reason", "unknown")

        return (
            "[HARD_STOP_TRIGGERED]\n"
            f"app={app_name}\n"
            f"market={market}\n"
            f"triggered_at={triggered_at}\n"
            f"restart_count={restart_count}\n"
            f"blocked_reason={blocked_reason}\n"
            f"safe_mode={boot_state.safe_mode}\n"
            f"hard_stop={boot_state.hard_stop}\n"
            f"trading_ready={boot_state.trading_ready}\n"
            f"failure_stage={boot_state.failure_stage}"
        )
