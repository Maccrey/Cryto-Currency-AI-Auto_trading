from fastapi.testclient import TestClient

from app.main import create_app


class SummaryStubService:
    def build(self, **kwargs):
        return {
            "coin_balance": 180.5,
            "cash_balance": 250000.0,
            "realized_pnl": 12500.0,
            "unrealized_pnl": -3200.0,
            "buy_count": 4,
            "sell_count": 3,
            "stop_loss_count": 1,
            "recent_stop_loss_reason": "STOP_LOSS_PRICE_HIT",
            "trading_mode": "demo",
            "learning_enabled": True,
            "safe_mode": False,
            "hard_stop": False,
            "trading_ready": True,
            "promotion_ready": False,
        }


def test_health_endpoint_reports_valid_mode(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "demo",
        "learning_enabled": True,
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "failure_stage": None,
    }


def test_summary_endpoint_returns_dashboard_panel_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            dashboard_summary_service=SummaryStubService(),
        ),
    )

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    assert response.json() == {
        "coin_balance": 180.5,
        "cash_balance": 250000.0,
        "realized_pnl": 12500.0,
        "unrealized_pnl": -3200.0,
        "buy_count": 4,
        "sell_count": 3,
        "stop_loss_count": 1,
        "recent_stop_loss_reason": "STOP_LOSS_PRICE_HIT",
        "trading_mode": "demo",
        "learning_enabled": True,
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "promotion_ready": False,
    }


def test_startup_sync_failure_keeps_safe_mode(monkeypatch) -> None:
    class FailingBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = False
                trading_ready = False
                failure_stage = "portfolio_sync"

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=FailingBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "mode": "demo",
        "learning_enabled": True,
        "safe_mode": True,
        "hard_stop": False,
        "trading_ready": False,
        "failure_stage": "portfolio_sync",
    }


def test_health_endpoint_reports_hard_stop_state(monkeypatch) -> None:
    class HardStopBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = True
                trading_ready = False
                failure_stage = "hard_stop"

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=HardStopBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "mode": "live",
        "learning_enabled": True,
        "safe_mode": True,
        "hard_stop": True,
        "trading_ready": False,
        "failure_stage": "hard_stop",
    }
