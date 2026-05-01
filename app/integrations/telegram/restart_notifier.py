from __future__ import annotations

import logging
from typing import Any

from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


class RestartMessageBuilder:
    """Build Telegram restart and recovery summary messages."""

    def build(
        self,
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
        market: str | None = None,
        trading_mode: str | None = None,
        learning_enabled: bool | None = None,
    ) -> str:
        portfolio = boot_state.portfolio_state
        cash_balance = portfolio.cash_balance if portfolio is not None else "unknown"
        asset_currency = portfolio.asset_currency if portfolio is not None else "unknown"
        asset_balance = portfolio.asset_balance if portfolio is not None else "unknown"
        status = "degraded" if boot_state.safe_mode or boot_state.hard_stop or not boot_state.trading_ready else "ok"

        return (
            "[SERVER_STARTED]\n"
            f"app={app_name}\n"
            f"started_at={restarted_at}\n"
            f"cause={cause}\n"
            f"status={status}\n"
            f"market={market or 'unknown'}\n"
            f"mode={trading_mode or 'unknown'}\n"
            f"learning_enabled={learning_enabled if learning_enabled is not None else 'unknown'}\n"
            f"safe_mode={boot_state.safe_mode}\n"
            f"hard_stop={boot_state.hard_stop}\n"
            f"trading_ready={boot_state.trading_ready}\n"
            f"failure_stage={boot_state.failure_stage}\n"
            f"cash_balance={cash_balance}\n"
            f"asset_currency={asset_currency}\n"
            f"asset_balance={asset_balance}"
        )


class RestartNotifier:
    """Send restart and recovery summaries through Telegram."""

    def __init__(
        self,
        *,
        gateway: Any,
        message_builder: RestartMessageBuilder | None = None,
    ) -> None:
        self._gateway = gateway
        self._message_builder = message_builder or RestartMessageBuilder()

    def notify_restarted(
        self,
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
        market: str | None = None,
        trading_mode: str | None = None,
        learning_enabled: bool | None = None,
    ) -> None:
        try:
            self._gateway.send_message(
                self._message_builder.build(
                    app_name=app_name,
                    restarted_at=restarted_at,
                    cause=cause,
                    boot_state=boot_state,
                    market=market,
                    trading_mode=trading_mode,
                    learning_enabled=learning_enabled,
                ),
            )
        except Exception:
            logger.exception(
                "telegram_restart_notification_failed",
                extra={
                    "app_name": app_name,
                    "market": market,
                    "trading_mode": trading_mode,
                    "cause": cause,
                },
            )
