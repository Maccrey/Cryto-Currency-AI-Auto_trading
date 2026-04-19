from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.services.notification.factory import build_notification_services


class RestartNotifierStub:
    def notify_restarted(self, **kwargs) -> None:
        pass


class HardStopNotifierStub:
    def notify_hard_stop(self, **kwargs) -> None:
        pass


def test_build_notification_services_returns_none_without_notifiers() -> None:
    services = build_notification_services()

    assert services.boot_notification_dispatcher is None


def test_build_notification_services_builds_dispatcher_from_notifiers() -> None:
    services = build_notification_services(
        restart_notifier=RestartNotifierStub(),
        hard_stop_notifier=HardStopNotifierStub(),
    )

    assert isinstance(services.boot_notification_dispatcher, BootNotificationDispatcher)


def test_build_notification_services_reuses_injected_dispatcher() -> None:
    dispatcher = BootNotificationDispatcher()

    services = build_notification_services(
        boot_notification_dispatcher=dispatcher,
        restart_notifier=RestartNotifierStub(),
        hard_stop_notifier=HardStopNotifierStub(),
    )

    assert services.boot_notification_dispatcher is dispatcher
