from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier
from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


class BootNotificationDispatcher:
    """Dispatch boot lifecycle notifications to the appropriate notifier."""

    def __init__(
        self,
        *,
        restart_notifier: RestartNotifier | None = None,
        hard_stop_notifier: HardStopNotifier | None = None,
        dashboard_url: str | None = None,
        settings_url: str | None = None,
        dedupe_store_path: Path | None = None,
        restart_cooldown_seconds: int = 600,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._restart_notifier = restart_notifier
        self._hard_stop_notifier = hard_stop_notifier
        self._dashboard_url = dashboard_url
        self._settings_url = settings_url
        self._dedupe_store_path = dedupe_store_path
        self._restart_cooldown_seconds = restart_cooldown_seconds
        self._clock = clock or time.time

    def dispatch_boot_event(
        self,
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        cause: str,
        boot_state: BootState,
        trading_mode: str | None = None,
        learning_enabled: bool | None = None,
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
        notification_key = "|".join([app_name, market, cause, trading_mode or "unknown"])
        if self._should_skip_restart_notification(notification_key):
            return
        self._restart_notifier.notify_restarted(
            app_name=app_name,
            restarted_at=triggered_at,
            cause=cause,
            boot_state=boot_state,
            market=market,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
            dashboard_url=self._dashboard_url,
            settings_url=self._settings_url,
        )
        self._record_restart_notification(notification_key)

    def _should_skip_restart_notification(self, notification_key: str) -> bool:
        if self._dedupe_store_path is None or self._restart_cooldown_seconds <= 0:
            return False
        state = self._read_dedupe_state()
        if state.get("notification_key") != notification_key:
            return False
        last_sent_at = state.get("sent_at_epoch")
        if not isinstance(last_sent_at, (int, float)):
            return False
        return self._clock() - float(last_sent_at) < self._restart_cooldown_seconds

    def _record_restart_notification(self, notification_key: str) -> None:
        if self._dedupe_store_path is None or self._restart_cooldown_seconds <= 0:
            return
        try:
            self._dedupe_store_path.parent.mkdir(parents=True, exist_ok=True)
            self._dedupe_store_path.write_text(
                json.dumps(
                    {
                        "notification_key": notification_key,
                        "sent_at_epoch": self._clock(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("telegram_boot_notification_dedupe_write_failed")

    def _read_dedupe_state(self) -> dict[str, object]:
        if self._dedupe_store_path is None or not self._dedupe_store_path.exists():
            return {}
        try:
            data = json.loads(self._dedupe_store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("telegram_boot_notification_dedupe_read_failed")
            return {}
        return data if isinstance(data, dict) else {}
