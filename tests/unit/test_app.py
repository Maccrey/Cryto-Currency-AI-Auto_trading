from fastapi.testclient import TestClient

from app.main import create_app
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult


class BootNotificationDispatcherStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def dispatch_boot_event(self, **kwargs) -> None:
        self.calls.append(kwargs)


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


class PromotionRunnerStub:
    def __init__(self, result: PromotionRunResult) -> None:
        self.result = result
        self.requests: list[object] = []

    def run(self, request) -> PromotionRunResult:
        self.requests.append(request)
        return self.result


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


def test_create_app_dispatches_boot_notification_when_boot_enters_hard_stop(monkeypatch) -> None:
    class HardStopBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = True
                trading_ready = False
                failure_stage = "hard_stop"
                portfolio_state = None
                reconcile_result = {
                    "restart_count": 3,
                    "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
                }

            return BootState()

    dispatcher = BootNotificationDispatcherStub()
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    create_app(
        recovery_orchestrator=HardStopBootOrchestrator(),
        boot_notification_dispatcher=dispatcher,
        timestamp_provider=lambda: "2026-04-18T12:30:00+09:00",
    )

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["app_name"] == "upbit-auto-trader"
    assert dispatcher.calls[0]["market"] == "KRW-XRP"
    assert dispatcher.calls[0]["triggered_at"] == "2026-04-18T12:30:00+09:00"
    assert dispatcher.calls[0]["cause"] == "process_restart"
    assert dispatcher.calls[0]["boot_state"].hard_stop is True
    assert dispatcher.calls[0]["boot_state"].failure_stage == "hard_stop"


def test_create_app_dispatches_boot_notification_when_boot_is_normal(monkeypatch) -> None:
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

    dispatcher = BootNotificationDispatcherStub()
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    create_app(
        recovery_orchestrator=SuccessfulBootOrchestrator(),
        boot_notification_dispatcher=dispatcher,
        timestamp_provider=lambda: "2026-04-18T12:35:00+09:00",
    )

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["cause"] == "process_restart"
    assert dispatcher.calls[0]["boot_state"].hard_stop is False


def test_promotion_review_endpoint_returns_runner_result(monkeypatch) -> None:
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

    runner = PromotionRunnerStub(
        PromotionRunResult(
            evaluation=PromotionEvaluation(
                status="READY_FOR_REVIEW",
                approved=False,
                rejection_reasons=[],
            ),
            approval_result=PromotionApprovalResult(
                live_enabled=True,
                safe_mode_entry=True,
                reason_code=None,
            ),
        ),
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
        ),
    )

    response = client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "evaluation": {
            "status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
        },
        "approval_result": {
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
        },
    }
    assert len(runner.requests) == 1
    assert runner.requests[0].market == "KRW-XRP"
    assert runner.requests[0].approval_granted is True


def test_promotion_status_endpoint_returns_empty_before_review(monkeypatch) -> None:
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

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/promotion/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "snapshot": None,
    }


def test_promotion_review_endpoint_uses_default_runner_when_not_injected(monkeypatch) -> None:
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

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["evaluation"] == {
        "status": "READY_FOR_REVIEW",
        "approved": False,
        "rejection_reasons": [],
    }
    assert response.json()["approval_result"] == {
        "live_enabled": True,
        "safe_mode_entry": True,
        "reason_code": None,
    }


def test_promotion_status_endpoint_returns_last_review_result(monkeypatch) -> None:
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

    runner = PromotionRunnerStub(
        PromotionRunResult(
            evaluation=PromotionEvaluation(
                status="READY_FOR_REVIEW",
                approved=False,
                rejection_reasons=[],
            ),
            approval_result=PromotionApprovalResult(
                live_enabled=True,
                safe_mode_entry=True,
                reason_code=None,
            ),
        ),
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
        ),
    )

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    response = client.get("/promotion/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "snapshot": {
            "market": "KRW-XRP",
            "evaluation_status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
            "reviewed_at": "2026-04-18T13:50:00+09:00",
        },
    }


def test_dashboard_summary_reflects_last_promotion_review_status(monkeypatch) -> None:
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

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    before_response = client.get("/dashboard/summary")

    assert before_response.status_code == 200
    assert before_response.json()["promotion_ready"] is False

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:55:00+09:00",
        },
    )

    after_response = client.get("/dashboard/summary")

    assert after_response.status_code == 200
    assert after_response.json()["promotion_ready"] is True
