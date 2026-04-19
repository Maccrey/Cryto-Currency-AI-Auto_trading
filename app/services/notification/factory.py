from __future__ import annotations

from dataclasses import dataclass

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.integrations.telegram.restart_notifier import RestartNotifier


@dataclass(frozen=True)
class NotificationServices:
    boot_notification_dispatcher: BootNotificationDispatcher | None


def build_notification_services(
    *,
    boot_notification_dispatcher: BootNotificationDispatcher | None = None,
    restart_notifier: RestartNotifier | None = None,
    hard_stop_notifier: HardStopNotifier | None = None,
) -> NotificationServices:
    if boot_notification_dispatcher is not None:
        return NotificationServices(
            boot_notification_dispatcher=boot_notification_dispatcher,
        )

    if restart_notifier is None and hard_stop_notifier is None:
        return NotificationServices(boot_notification_dispatcher=None)

    return NotificationServices(
        boot_notification_dispatcher=BootNotificationDispatcher(
            restart_notifier=restart_notifier,
            hard_stop_notifier=hard_stop_notifier,
        ),
    )
