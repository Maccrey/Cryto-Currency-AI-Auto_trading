from pathlib import Path

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.services.learning.service import LearningService
from app.services.recovery.orchestrator import BootState
from app.services.runtime.factory import build_runtime_services
from app.services.recovery.orchestrator import FileRestartStateStore, RecoveryOrchestrator


class RecoveryOrchestratorStub:
    def boot(self):
        return None


class BootDispatcherStub(BootNotificationDispatcher):
    def __init__(self) -> None:
        super().__init__()


def test_build_runtime_services_uses_virtual_portfolio_in_demo(
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
        restart_state_path=tmp_path / "restart-state.json",
        timestamp_provider=lambda: "2026-04-19T19:00:00+09:00",
        learning_service=LearningService(log_dir=tmp_path),
    )

    state = services.runtime_service.start()

    assert state.portfolio_state is not None
    assert state.portfolio_state.cash_balance == 1_000_000.0
    assert state.portfolio_state.asset_currency == "XRP"
    assert state.reconcile_result == {"open_order_count": 0, "status": "demo_skipped"}


def test_build_runtime_services_allows_demo_without_upbit_api_keys(tmp_path: Path) -> None:
    services = build_runtime_services(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        upbit_base_url="https://api.upbit.com",
        upbit_access_key="",
        upbit_secret_key="",
        trade_coin="XRP",
        trade_market="KRW-XRP",
        restart_state_path=tmp_path / "restart-state.json",
        timestamp_provider=lambda: "2026-04-19T19:00:00+09:00",
        learning_service=LearningService(log_dir=tmp_path),
    )

    state = services.runtime_service.start()

    assert state == BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=state.portfolio_state,
        reconcile_result={"open_order_count": 0, "status": "demo_skipped"},
    )
    assert state.portfolio_state is not None
    assert state.portfolio_state.cash_balance == 1_000_000.0


def test_build_runtime_services_live_without_keys_starts_in_safe_mode(tmp_path: Path) -> None:
    services = build_runtime_services(
        app_name="upbit-auto-trader",
        trading_mode="live",
        upbit_base_url="https://api.upbit.com",
        upbit_access_key="",
        upbit_secret_key="",
        trade_coin="XRP",
        trade_market="KRW-XRP",
        restart_state_path=tmp_path / "restart-state.json",
        timestamp_provider=lambda: "2026-04-19T19:00:00+09:00",
        learning_service=LearningService(log_dir=tmp_path),
    )

    state = services.runtime_service.start()

    assert state.safe_mode is True
    assert state.trading_ready is False
    assert state.failure_stage == "api_key_missing"


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
        restart_state_path=None,
        timestamp_provider=lambda: "2026-04-19T19:05:00+09:00",
        boot_notification_dispatcher=dispatcher,
        recovery_orchestrator=orchestrator,
    )

    assert services.recovery_orchestrator is orchestrator
    assert services.runtime_service is not None
