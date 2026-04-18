from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_valid_mode(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
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
        "trading_ready": True,
        "failure_stage": None,
    }


def test_startup_sync_failure_keeps_safe_mode(monkeypatch) -> None:
    class FailingBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
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
        "trading_ready": False,
        "failure_stage": "portfolio_sync",
    }
