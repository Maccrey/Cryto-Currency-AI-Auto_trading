from __future__ import annotations

from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier
from app.services.recovery.orchestrator import BootState


class BootNotificationDispatcher:
    """Dispatch boot lifecycle notifications to the appropriate notifier."""

    def __init__(
        self,
        *,
        restart_notifier: RestartNotifier | None = None,
        hard_stop_notifier: HardStopNotifier | None = None,
    ) -> None:
        self._restart_notifier = restart_notifier
        self._hard_stop_notifier = hard_stop_notifier

    def dispatch_boot_event(
        self,
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        cause: str,
        boot_state: BootState,
    ) -> None:
        if boot_state.hard_stop:
            if self._hard_stop_notifier is None:
                return
            self._hard_stop_notifier.notify_hard_stop(
                app_name=app_name,
                market=market,
                triggered_at=triggered_at,
                boot_state=boot_state,
            )
            return

        if self._restart_notifier is None:
            return
        self._restart_notifier.notify_restarted(
            app_name=app_name,
            restarted_at=triggered_at,
            cause=cause,
            boot_state=boot_state,
        )
