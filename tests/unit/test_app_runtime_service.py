from app.services.runtime.service import AppRuntimeService


class RecoveryOrchestratorStub:
    def __init__(self, boot_state) -> None:
        self._boot_state = boot_state
        self.boot_calls = 0

    def boot(self):
        self.boot_calls += 1
        return self._boot_state


class BootNotificationDispatcherStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def dispatch_boot_event(self, **kwargs) -> None:
        self.calls.append(kwargs)


class BootStateStub:
    safe_mode = False
    hard_stop = False
    trading_ready = True
    failure_stage = None


def test_app_runtime_service_starts_boot_and_dispatches_notification() -> None:
    boot_state = BootStateStub()
    orchestrator = RecoveryOrchestratorStub(boot_state)
    dispatcher = BootNotificationDispatcherStub()
    service = AppRuntimeService(
        recovery_orchestrator=orchestrator,
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        trading_mode="demo",
        learning_enabled=True,
        timestamp_provider=lambda: "2026-04-19T19:10:00+09:00",
        boot_notification_dispatcher=dispatcher,
    )

    result = service.start()

    assert result is boot_state
    assert orchestrator.boot_calls == 1
    assert dispatcher.calls == [
        {
            "app_name": "upbit-auto-trader",
            "market": "KRW-XRP",
            "triggered_at": "2026-04-19T19:10:00+09:00",
            "cause": "process_restart",
            "boot_state": boot_state,
            "trading_mode": "demo",
            "learning_enabled": True,
        }
    ]


def test_app_runtime_service_skips_dispatch_without_notifier() -> None:
    boot_state = BootStateStub()
    orchestrator = RecoveryOrchestratorStub(boot_state)
    service = AppRuntimeService(
        recovery_orchestrator=orchestrator,
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        trading_mode="demo",
        learning_enabled=True,
        timestamp_provider=lambda: "2026-04-19T19:15:00+09:00",
    )

    result = service.start()

    assert result is boot_state
    assert orchestrator.boot_calls == 1


def test_app_runtime_service_can_defer_boot_notification() -> None:
    boot_state = BootStateStub()
    orchestrator = RecoveryOrchestratorStub(boot_state)
    dispatcher = BootNotificationDispatcherStub()
    service = AppRuntimeService(
        recovery_orchestrator=orchestrator,
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        trading_mode="demo",
        learning_enabled=True,
        timestamp_provider=lambda: "2026-04-19T19:20:00+09:00",
        boot_notification_dispatcher=dispatcher,
        dispatch_boot_notification_on_start=False,
    )

    result = service.start()

    assert result is boot_state
    assert dispatcher.calls == []

    service.dispatch_boot_notification(boot_state=boot_state)

    assert dispatcher.calls[0]["boot_state"] is boot_state
    assert dispatcher.calls[0]["cause"] == "process_restart"
