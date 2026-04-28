from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.recovery.hard_stop import RestartCounter
from app.services.recovery.orchestrator import FileRestartStateStore, RecoveryOrchestrator


class StubRestartStore:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def record(self, event: dict[str, object]) -> None:
        self.events.append(event)


class SuccessfulPortfolioSyncService:
    def sync(self) -> PortfolioState:
        return PortfolioState(
            cash_balance=150000.0,
            asset_currency="XRP",
            asset_balance=120.0,
            avg_buy_price=820.0,
        )


class FailingPortfolioSyncService:
    def sync(self) -> PortfolioState:
        raise RuntimeError("portfolio sync failed")


class SuccessfulOpenOrderReconciler:
    def reconcile(self) -> dict[str, object]:
        return {"open_order_count": 0}


class FailingOpenOrderReconciler:
    def reconcile(self) -> dict[str, object]:
        raise RuntimeError("reconcile failed")


def test_recovery_orchestrator_records_restart_and_enables_trading() -> None:
    restart_store = StubRestartStore()
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=restart_store,
    )

    state = orchestrator.boot()

    assert restart_store.events == [
        {
            "event_name": "restart_detected",
            "app_name": "upbit-auto-trader",
            "trading_mode": "demo",
        }
    ]
    assert state.safe_mode is False
    assert state.hard_stop is False
    assert state.trading_ready is True
    assert state.portfolio_state is not None
    assert state.reconcile_result == {"open_order_count": 0}


def test_recovery_orchestrator_blocks_trading_when_portfolio_sync_fails() -> None:
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="demo",
        portfolio_sync_service=FailingPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=StubRestartStore(),
    )

    state = orchestrator.boot()

    assert state.safe_mode is True
    assert state.hard_stop is False
    assert state.trading_ready is False
    assert state.failure_stage == "portfolio_sync"


def test_recovery_orchestrator_keeps_safe_mode_when_reconcile_fails() -> None:
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="live",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=FailingOpenOrderReconciler(),
        restart_store=StubRestartStore(),
    )

    state = orchestrator.boot()

    assert state.safe_mode is True
    assert state.hard_stop is False
    assert state.trading_ready is False
    assert state.failure_stage == "open_order_reconcile"
    assert state.portfolio_state is not None


def test_recovery_orchestrator_enters_hard_stop_when_restart_threshold_is_hit() -> None:
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="live",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=StubRestartStore(),
        restart_counter=RestartCounter(threshold=1),
    )

    state = orchestrator.boot()

    assert state.safe_mode is True
    assert state.hard_stop is True
    assert state.trading_ready is False
    assert state.failure_stage == "hard_stop"
    assert state.portfolio_state is None
    assert state.reconcile_result == {
        "restart_count": 1,
        "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
    }


def test_recovery_orchestrator_records_hard_stop_learning_event() -> None:
    class StubLearningService:
        def __init__(self) -> None:
            self.events = []

        def record(self, event) -> None:
            self.events.append(event)

    learning_service = StubLearningService()
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="live",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=StubRestartStore(),
        restart_counter=RestartCounter(threshold=1),
        learning_service=learning_service,
    )

    state = orchestrator.boot()

    assert state.hard_stop is True
    assert [event.event_name for event in learning_service.events] == [
        "restart_detected",
        "hard_stop_triggered",
    ]


def test_file_restart_state_store_persists_latest_boot_state(tmp_path) -> None:
    store = FileRestartStateStore(tmp_path / "restart-state.json")
    orchestrator = RecoveryOrchestrator(
        app_name="upbit-auto-trader",
        trading_mode="live",
        portfolio_sync_service=SuccessfulPortfolioSyncService(),
        open_order_reconciler=SuccessfulOpenOrderReconciler(),
        restart_store=store,
    )

    state = orchestrator.boot()

    persisted = store.load_latest()
    assert state.trading_ready is True
    assert persisted["event_name"] == "recovery_completed"
    assert persisted["safe_mode"] is False
    assert persisted["trading_ready"] is True
    assert persisted["reconcile_result"] == {"open_order_count": 0}
