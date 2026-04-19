from pathlib import Path

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.services.learning.service import LearningService
from app.services.runtime.factory import build_runtime_services
from app.services.recovery.orchestrator import RecoveryOrchestrator


class RecoveryOrchestratorStub:
    def boot(self):
        return None


class BootDispatcherStub(BootNotificationDispatcher):
    def __init__(self) -> None:
        super().__init__()


def test_build_runtime_services_creates_default_recovery_orchestrator(
    tmp_path: Path,
) -> None:
    services = build_runtime_services(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        upbit_base_url="https://api.upbit.com",
        upbit_access_key="access",
        upbit_secret_key="secret",
        trade_coin="XRP",
        trade_market="KRW-XRP",
        timestamp_provider=lambda: "2026-04-19T19:00:00+09:00",
        learning_service=LearningService(log_dir=tmp_path),
    )

    assert isinstance(services.recovery_orchestrator, RecoveryOrchestrator)
    assert services.runtime_service is not None


def test_build_runtime_services_reuses_injected_recovery_orchestrator() -> None:
    orchestrator = RecoveryOrchestratorStub()
    dispatcher = BootDispatcherStub()

    services = build_runtime_services(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        upbit_base_url="https://api.upbit.com",
        upbit_access_key="access",
        upbit_secret_key="secret",
        trade_coin="XRP",
        trade_market="KRW-XRP",
        timestamp_provider=lambda: "2026-04-19T19:05:00+09:00",
        boot_notification_dispatcher=dispatcher,
        recovery_orchestrator=orchestrator,
    )

    assert services.recovery_orchestrator is orchestrator
    assert services.runtime_service is not None
