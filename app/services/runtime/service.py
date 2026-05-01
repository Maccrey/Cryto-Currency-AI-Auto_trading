from __future__ import annotations

from collections.abc import Callable

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.services.recovery.orchestrator import BootState, RecoveryOrchestrator


class AppRuntimeService:
    """Start runtime boot flow and emit operational boot notifications."""

    def __init__(
        self,
        *,
        recovery_orchestrator: RecoveryOrchestrator,
        app_name: str,
        market: str,
        trading_mode: str,
        learning_enabled: bool,
        timestamp_provider: Callable[[], str],
        boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    ) -> None:
        self._recovery_orchestrator = recovery_orchestrator
        self._app_name = app_name
        self._market = market
        self._trading_mode = trading_mode
        self._learning_enabled = learning_enabled
        self._timestamp_provider = timestamp_provider
        self._boot_notification_dispatcher = boot_notification_dispatcher

    def start(self) -> BootState:
        boot_state = self._recovery_orchestrator.boot()
        if self._boot_notification_dispatcher is not None:
            self._boot_notification_dispatcher.dispatch_boot_event(
                app_name=self._app_name,
                market=self._market,
                triggered_at=self._timestamp_provider(),
                cause="process_restart",
                boot_state=boot_state,
                trading_mode=self._trading_mode,
                learning_enabled=self._learning_enabled,
            )
        return boot_state
