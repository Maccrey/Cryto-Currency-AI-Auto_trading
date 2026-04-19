from pathlib import Path

from app.services.learning.service import LearningService
from app.services.runtime.factory import build_runtime_services
from app.services.recovery.orchestrator import RecoveryOrchestrator


class RecoveryOrchestratorStub:
    def boot(self):
        return None


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
        learning_service=LearningService(log_dir=tmp_path),
    )

    assert isinstance(services.recovery_orchestrator, RecoveryOrchestrator)


def test_build_runtime_services_reuses_injected_recovery_orchestrator() -> None:
    orchestrator = RecoveryOrchestratorStub()

    services = build_runtime_services(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        upbit_base_url="https://api.upbit.com",
        upbit_access_key="access",
        upbit_secret_key="secret",
        trade_coin="XRP",
        trade_market="KRW-XRP",
        recovery_orchestrator=orchestrator,
    )

    assert services.recovery_orchestrator is orchestrator
