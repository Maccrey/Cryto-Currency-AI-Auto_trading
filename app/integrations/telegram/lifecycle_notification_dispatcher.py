from __future__ import annotations

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.promotion_notifier import PromotionNotifier
from app.services.recovery.orchestrator import BootState


class LifecycleNotificationDispatcher:
    """Route operational lifecycle events to the appropriate Telegram notifier."""

    def __init__(
        self,
        *,
        boot_dispatcher: BootNotificationDispatcher | None = None,
        promotion_notifier: PromotionNotifier | None = None,
    ) -> None:
        self._boot_dispatcher = boot_dispatcher
        self._promotion_notifier = promotion_notifier

    def dispatch_boot_event(
        self,
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        cause: str,
        boot_state: BootState,
    ) -> None:
        if self._boot_dispatcher is None:
            return
        self._boot_dispatcher.dispatch_boot_event(
            app_name=app_name,
            market=market,
            triggered_at=triggered_at,
            cause=cause,
            boot_state=boot_state,
        )

    def dispatch_promotion_ready(
        self,
        *,
        market: str,
        demo_days: int,
        total_trades: int,
        profit_factor: float,
        max_drawdown: float,
    ) -> None:
        if self._promotion_notifier is None:
            return
        self._promotion_notifier.notify_ready(
            market=market,
            demo_days=demo_days,
            total_trades=total_trades,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
        )

    def dispatch_live_enabled(
        self,
        *,
        market: str,
        approved_by: str,
        activated_at: str,
    ) -> None:
        if self._promotion_notifier is None:
            return
        self._promotion_notifier.notify_live_enabled(
            market=market,
            approved_by=approved_by,
            activated_at=activated_at,
        )
