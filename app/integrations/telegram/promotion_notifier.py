from __future__ import annotations

from typing import Any


class PromotionNotifier:
    """Send promotion-related lifecycle messages through Telegram."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_ready(
        self,
        *,
        market: str,
        demo_days: int,
        total_trades: int,
        profit_factor: float,
        max_drawdown: float,
    ) -> None:
        self._gateway.send_message(
            "[PROMOTION_READY]\n"
            f"market={market}\n"
            f"demo_days={demo_days}\n"
            f"total_trades={total_trades}\n"
            f"profit_factor={profit_factor}\n"
            f"max_drawdown={max_drawdown}"
        )

    def notify_live_enabled(
        self,
        *,
        market: str,
        approved_by: str,
        activated_at: str,
    ) -> None:
        self._gateway.send_message(
            "[LIVE_MODE_ENABLED]\n"
            f"market={market}\n"
            f"approved_by={approved_by}\n"
            f"activated_at={activated_at}"
        )
