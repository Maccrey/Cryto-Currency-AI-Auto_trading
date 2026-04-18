from __future__ import annotations

from typing import Any

from app.services.recovery.orchestrator import BootState


class RestartNotifier:
    """Send restart and recovery summaries through Telegram."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_restarted(
        self,
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
    ) -> None:
        self._gateway.send_message(
            self._build_message(
                app_name=app_name,
                restarted_at=restarted_at,
                cause=cause,
                boot_state=boot_state,
            ),
        )

    @staticmethod
    def _build_message(
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
    ) -> str:
        portfolio = boot_state.portfolio_state
        cash_balance = portfolio.cash_balance if portfolio is not None else "unknown"
        asset_currency = portfolio.asset_currency if portfolio is not None else "unknown"
        asset_balance = portfolio.asset_balance if portfolio is not None else "unknown"

        return (
            "[RESTARTED]\n"
            f"app={app_name}\n"
            f"restarted_at={restarted_at}\n"
            f"cause={cause}\n"
            f"safe_mode={boot_state.safe_mode}\n"
            f"trading_ready={boot_state.trading_ready}\n"
            f"failure_stage={boot_state.failure_stage}\n"
            f"cash_balance={cash_balance}\n"
            f"asset_currency={asset_currency}\n"
            f"asset_balance={asset_balance}"
        )
