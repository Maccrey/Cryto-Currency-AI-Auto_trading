from fastapi.testclient import TestClient

from app.main import create_app
from app.services.learning.service import LearningEvent
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
            "last_learning_event": "position_opened",
            "learning_signal_count": 3,
            "learning_fill_count": 2,
            "last_signal_recorded_at": "2026-04-19T20:00:00+09:00",
            "last_fill_recorded_at": "2026-04-19T20:00:01+09:00",
            "last_position_event": "opened",
            "last_promotion_reviewed_at": "2026-04-19T20:00:02+09:00",
            "last_restart_detected_at": "2026-04-19T20:00:03+09:00",
            "last_recovery_completed_at": "2026-04-19T20:00:04+09:00",
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


class LearningServiceStub:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)

    def recent_events(self, *, limit: int | None = None) -> list[LearningEvent]:
        if limit is None or limit >= len(self.events):
            return list(self.events)
        return self.events[-limit:]


class TelegramNotifierStub:
    def __init__(self) -> None:
        self.fills = []

    def notify_fill(self, fill) -> None:
        self.fills.append(fill)


class TradeDecisionServiceStub:
    def evaluate(self, request):
        self.request = request
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        }


class TradeExecutionServiceStub:
    def execute(self, decision):
        self.decision = decision
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "status": "filled",
            "blocked_reason": None,
            "execution": {
                "market": "KRW-XRP",
                "side": "buy",
                "filled_price": 800.0,
                "filled_quantity": 192.5,
                "mode": "demo",
                "is_virtual": True,
            },
        }


class PostFillServiceStub:
    def process(self, execution_result):
        self.execution_result = execution_result
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "execution": {
                "status": "filled",
                "blocked_reason": None,
                "execution": {
                    "market": "KRW-XRP",
                    "side": "buy",
                    "filled_price": 800.0,
                    "filled_quantity": 192.5,
                    "mode": "demo",
                    "is_virtual": True,
                },
            },
            "position": {
                "market": "KRW-XRP",
                "signal_level": "strong",
                "entry_price": 800.0,
                "quantity": 192.5,
                "stop_loss_price": 785.6,
                "stop_loss_pct": 0.018,
                "validation_window_sec": 180,
                "min_expected_return_pct": 0.004,
                "stop_loss_reason": None,
            },
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
        "last_learning_event": "position_opened",
        "learning_signal_count": 3,
        "learning_fill_count": 2,
        "last_signal_recorded_at": "2026-04-19T20:00:00+09:00",
        "last_fill_recorded_at": "2026-04-19T20:00:01+09:00",
        "last_position_event": "opened",
        "last_promotion_reviewed_at": "2026-04-19T20:00:02+09:00",
        "last_restart_detected_at": "2026-04-19T20:00:03+09:00",
        "last_recovery_completed_at": "2026-04-19T20:00:04+09:00",
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "promotion_ready": False,
    }


def test_decision_entry_endpoint_returns_trade_decision_payload(monkeypatch) -> None:
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
    trade_decision_service = TradeDecisionServiceStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_decision_service=trade_decision_service,
        ),
    )

    response = client.post(
        "/decision/entry",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "decision": {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        },
    }


def test_decision_execute_endpoint_returns_execution_payload(monkeypatch) -> None:
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
    trade_decision_service = TradeDecisionServiceStub()
    trade_execution_service = TradeExecutionServiceStub()
    post_fill_service = PostFillServiceStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_decision_service=trade_decision_service,
            trade_execution_service=trade_execution_service,
            post_fill_service=post_fill_service,
        ),
    )

    response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "decision": {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        },
        "execution": {
            "status": "filled",
            "blocked_reason": None,
            "execution": {
                "market": "KRW-XRP",
                "side": "buy",
                "filled_price": 800.0,
                "filled_quantity": 192.5,
                "mode": "demo",
                "is_virtual": True,
            },
        },
        "post_fill": {
            "execution": {
                "status": "filled",
                "blocked_reason": None,
                "execution": {
                    "market": "KRW-XRP",
                    "side": "buy",
                    "filled_price": 800.0,
                    "filled_quantity": 192.5,
                    "mode": "demo",
                    "is_virtual": True,
                },
            },
            "position": {
                "market": "KRW-XRP",
                "signal_level": "strong",
                "entry_price": 800.0,
                "quantity": 192.5,
                "stop_loss_price": 785.6,
                "stop_loss_pct": 0.018,
                "validation_window_sec": 180,
                "min_expected_return_pct": 0.004,
                "stop_loss_reason": None,
            },
        },
    }


def test_decision_execute_notifies_buy_fill(monkeypatch) -> None:
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
    trade_fill_notifier = TelegramNotifierStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_fill_notifier=trade_fill_notifier,
        ),
    )

    response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert len(trade_fill_notifier.fills) == 1
    assert trade_fill_notifier.fills[0].side == "buy"
    assert trade_fill_notifier.fills[0].is_stop_loss is False


def test_position_endpoints_return_saved_position_and_overlay(monkeypatch) -> None:
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
        ),
    )

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    position_response = client.get("/position/current")
    overlay_response = client.get("/position/overlay/stop-loss")

    assert position_response.status_code == 200
    assert overlay_response.status_code == 200
    assert position_response.json()["status"] == "ok"
    assert position_response.json()["position"]["market"] == "KRW-XRP"
    assert overlay_response.json() == {
        "status": "ok",
        "overlay": {
            "active": True,
            "market": "KRW-XRP",
            "stop_loss_price": position_response.json()["position"]["stop_loss_price"],
            "label": "STOP LOSS",
        },
    }

    risk_response = client.post(
        "/position/risk-check",
        json={
            "current_price": position_response.json()["position"]["stop_loss_price"] - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert risk_response.status_code == 200
    assert risk_response.json()["status"] == "ok"
    assert risk_response.json()["hard_stop"]["triggered"] is True
    assert (
        risk_response.json()["post_entry"]["reason_code"]
        == "STOP_LOSS_EXPECTATION_FAILED"
    )

    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": position_response.json()["position"]["stop_loss_price"] - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert exit_response.status_code == 200
    assert exit_response.json()["status"] == "ok"
    assert exit_response.json()["trigger"] == {
        "type": "hard_stop",
        "reason_code": "STOP_LOSS_PRICE_HIT",
        "exit_ratio": 1.0,
    }
    assert exit_response.json()["execution"]["side"] == "sell"
    assert exit_response.json()["execution"]["is_stop_loss"] is True
    assert client.get("/position/current").json() == {
        "status": "empty",
        "position": None,
    }


def test_position_exit_records_learning_event_and_notifies_fill(monkeypatch) -> None:
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
    learning_service = LearningServiceStub()
    trade_fill_notifier = TelegramNotifierStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            learning_service=learning_service,
            trade_fill_notifier=trade_fill_notifier,
        ),
    )

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert exit_response.status_code == 200
    assert len(trade_fill_notifier.fills) == 2
    assert trade_fill_notifier.fills[0].side == "buy"
    assert trade_fill_notifier.fills[-1].side == "sell"
    assert trade_fill_notifier.fills[-1].is_stop_loss is True
    assert [event.event_name for event in learning_service.events][-4:] == [
        "position_opened",
        "fill_result",
        "position_exit_completed",
        "position_lifecycle_updated",
    ]
    assert learning_service.events[-2].payload["trigger_type"] == "hard_stop"
    assert learning_service.events[-1].payload["event_type"] == "closed"


def test_summary_endpoint_reflects_runtime_execution_counts(monkeypatch) -> None:
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
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    summary_response = client.get("/dashboard/summary")

    assert summary_response.status_code == 200
    assert summary_response.json()["buy_count"] == 1
    assert summary_response.json()["sell_count"] == 1
    assert summary_response.json()["stop_loss_count"] == 1
    assert summary_response.json()["recent_stop_loss_reason"] == "STOP_LOSS_PRICE_HIT"
    assert summary_response.json()["realized_pnl"] < 0.0


def test_summary_endpoint_reflects_unrealized_pnl_from_latest_price(monkeypatch) -> None:
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
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    risk_response = client.post(
        "/position/risk-check",
        json={
            "current_price": 845.0,
            "elapsed_sec": 60,
            "momentum_score": 0.6,
            "orderbook_imbalance": 0.1,
        },
    )
    assert risk_response.status_code == 200

    summary_response = client.get("/dashboard/summary")

    assert summary_response.status_code == 200
    assert summary_response.json()["unrealized_pnl"] > 0.0


def test_market_current_endpoint_returns_latest_snapshot(monkeypatch) -> None:
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
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:10:00+09:00",
        ),
    )

    empty_response = client.get("/market/current")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "snapshot": None,
    }

    entry_response = client.post(
        "/decision/entry",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert entry_response.status_code == 200

    current_response = client.get("/market/current")

    assert current_response.status_code == 200
    assert current_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "snapshot": {
            "market": "KRW-XRP",
            "price": 820.0,
            "recorded_at": "2026-04-19T20:10:00+09:00",
        },
    }


def test_market_history_endpoint_returns_recent_snapshots(monkeypatch) -> None:
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

    timestamps = iter(
        [
            "2026-04-19T20:20:00+09:00",
            "2026-04-19T20:20:01+09:00",
            "2026-04-19T20:20:02+09:00",
        ],
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: next(timestamps),
        ),
    )

    empty_response = client.get("/market/history")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "history": [],
    }

    for price in [820.0, 825.0, 830.0]:
        response = client.post(
            "/decision/entry",
            json={
                "prices": [800.0, 806.0, 813.0, price],
                "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
                "spread_bps": 8.0,
                "orderbook_imbalance": 0.24,
                "liquidity_score": 0.9,
                "regime_score": 0.78,
                "current_price": price,
                "slippage_bps": 10.0,
                "portfolio": {
                    "cash_balance": 500000.0,
                    "asset_currency": "XRP",
                    "asset_balance": 0.0,
                    "avg_buy_price": 0.0,
                },
                "safe_mode": False,
                "recent_loss_streak": 0,
            },
        )
        assert response.status_code == 200

    history_response = client.get("/market/history?limit=2")

    assert history_response.status_code == 200
    assert history_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "history": [
            {
                "market": "KRW-XRP",
                "price": 825.0,
                "recorded_at": "2026-04-19T20:20:01+09:00",
            },
            {
                "market": "KRW-XRP",
                "price": 830.0,
                "recorded_at": "2026-04-19T20:20:02+09:00",
            },
        ],
    }


def test_learning_recent_endpoint_returns_runtime_events(monkeypatch) -> None:
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
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:30:00+09:00",
        ),
    )

    response = client.get("/learning/recent")
    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "events": [],
    }

    execution_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execution_response.status_code == 200

    response = client.get("/learning/recent?limit=4")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["market"] == "KRW-XRP"
    assert [event["event_name"] for event in response.json()["events"]] == [
        "signal_generated",
        "fill_result",
        "position_opened",
    ]


def test_dashboard_market_endpoint_returns_market_summary(monkeypatch) -> None:
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

    timestamps = iter(
        [
            "2026-04-19T20:40:00+09:00",
            "2026-04-19T20:40:01+09:00",
            "2026-04-19T20:40:02+09:00",
        ],
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: next(timestamps),
        ),
    )

    for price in [820.0, 825.0, 830.0]:
        response = client.post(
            "/decision/entry",
            json={
                "prices": [800.0, 806.0, 813.0, price],
                "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
                "spread_bps": 8.0,
                "orderbook_imbalance": 0.24,
                "liquidity_score": 0.9,
                "regime_score": 0.78,
                "current_price": price,
                "slippage_bps": 10.0,
                "portfolio": {
                    "cash_balance": 500000.0,
                    "asset_currency": "XRP",
                    "asset_balance": 0.0,
                    "avg_buy_price": 0.0,
                },
                "safe_mode": False,
                "recent_loss_streak": 0,
            },
        )
        assert response.status_code == 200

    dashboard_response = client.get("/dashboard/market?history_limit=2")

    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "summary": {
            "market": "KRW-XRP",
            "current_price": 830.0,
            "recorded_at": "2026-04-19T20:40:02+09:00",
            "recent_change_pct": 0.0061,
            "history": [
                {
                    "market": "KRW-XRP",
                    "price": 825.0,
                    "recorded_at": "2026-04-19T20:40:01+09:00",
                },
                {
                    "market": "KRW-XRP",
                    "price": 830.0,
                    "recorded_at": "2026-04-19T20:40:02+09:00",
                },
            ],
        },
    }


def test_dashboard_learning_endpoint_returns_learning_summary(monkeypatch) -> None:
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
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:45:00+09:00",
        ),
    )

    empty_response = client.get("/dashboard/learning")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "learning": None,
    }

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    response = client.get("/dashboard/learning?limit=2")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["learning"]["total_events"] == 2
    assert response.json()["learning"]["last_event_name"] == "position_opened"
    assert response.json()["learning"]["event_counts"] == {
        "fill_result": 1,
        "position_opened": 1,
    }
    assert [event["event_name"] for event in response.json()["learning"]["recent_events"]] == [
        "fill_result",
        "position_opened",
    ]


def test_dashboard_learning_health_endpoint_returns_category_summary(monkeypatch) -> None:
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
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:46:00+09:00",
        ),
    )

    empty_response = client.get("/dashboard/learning/health")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "health": None,
    }

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    response = client.get("/dashboard/learning/health?limit=3")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["health"]["total_events"] == 3
    assert response.json()["health"]["category_counts"] == {
        "signals": 1,
        "fills": 1,
        "positions": 1,
    }


def test_dashboard_recovery_endpoint_returns_recovery_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            from app.services.recovery.orchestrator import BootState

            return BootState(
                safe_mode=False,
                hard_stop=False,
                trading_ready=True,
                failure_stage=None,
                portfolio_state=None,
                reconcile_result=None,
            )

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")
    learning_service = LearningServiceStub()
    learning_service.record(
        LearningEvent(
            event_name="restart_detected",
            market="KRW-XRP",
            mode="demo",
            payload={"app_name": "test-app"},
            recorded_at="2026-04-20T10:00:00+09:00",
        ),
    )

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            learning_service=learning_service,
            timestamp_provider=lambda: "2026-04-20T10:00:00+09:00",
        ),
    )

    response = client.get("/dashboard/recovery")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["recovery"]["state_label"] == "OK"
    assert response.json()["recovery"]["state_message"] == "정상 복구가 완료되어 거래 가능 상태입니다."
    assert response.json()["recovery"]["recommended_action"] == "추가 조치 없이 운영을 지속할 수 있습니다."
    assert response.json()["recovery"]["safe_mode"] is False
    assert response.json()["recovery"]["hard_stop"] is False
    assert response.json()["recovery"]["trading_ready"] is True
    assert response.json()["recovery"]["restart_count"] is None
    assert response.json()["recovery"]["blocked_reason"] is None
    assert response.json()["recovery"]["last_restart_detected_at"] == "2026-04-20T10:00:00+09:00"
    assert response.json()["recovery"]["hard_stop_triggered_at"] is None
    assert response.json()["recovery"]["recent_events"][0]["event_name"] == "restart_detected"
    assert response.json()["recovery"]["recent_recovery_timeline"] == [
        {
            "event_name": "restart_detected",
            "occurred_at": "2026-04-20T10:00:00+09:00",
            "app_name": "test-app",
            "trading_mode": None,
            "safe_mode": None,
            "trading_ready": None,
            "failure_stage": None,
            "open_order_count": None,
        },
    ]
    assert response.json()["recovery"]["recent_hard_stop_events"] == []
    assert response.json()["recovery"]["recent_hard_stop_timeline"] == []
    assert response.json()["recovery"]["recovery_timeline"] == [
        {
            "event_name": "restart_detected",
            "occurred_at": "2026-04-20T10:00:00+09:00",
            "app_name": "test-app",
            "trading_mode": None,
            "safe_mode": None,
            "trading_ready": None,
            "failure_stage": None,
            "open_order_count": None,
            "restart_count": None,
            "blocked_reason": None,
        },
    ]
    assert response.json()["recovery"]["current_state_summary"] == {
        "state_label": "OK",
        "state_message": "정상 복구가 완료되어 거래 가능 상태입니다.",
        "recommended_action": "추가 조치 없이 운영을 지속할 수 있습니다.",
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "failure_stage": None,
        "restart_count": None,
        "blocked_reason": None,
        "last_restart_detected_at": "2026-04-20T10:00:00+09:00",
        "last_recovery_completed_at": None,
        "hard_stop_triggered_at": None,
    }


def test_dashboard_executions_endpoint_returns_recent_fill_history(monkeypatch) -> None:
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
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    history_response = client.get("/dashboard/executions?limit=2")

    assert history_response.status_code == 200
    assert history_response.json()["status"] == "ok"
    assert len(history_response.json()["history"]) == 2
    assert history_response.json()["history"][0]["side"] == "buy"
    assert history_response.json()["history"][1]["side"] == "sell"
    assert history_response.json()["history"][1]["reason_code"] == "STOP_LOSS_PRICE_HIT"


def test_dashboard_positions_history_endpoint_returns_position_lifecycle(monkeypatch) -> None:
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
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    history_response = client.get("/dashboard/positions/history?limit=2")

    assert history_response.status_code == 200
    assert history_response.json()["status"] == "ok"
    assert len(history_response.json()["history"]) == 2
    assert history_response.json()["history"][0]["event_type"] == "opened"
    assert history_response.json()["history"][1]["event_type"] == "closed"
    assert history_response.json()["history"][1]["reason_code"] == "STOP_LOSS_PRICE_HIT"


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


def test_promotion_review_endpoint_records_learning_event(monkeypatch) -> None:
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
    learning_service = LearningServiceStub()
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
            learning_service=learning_service,
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
            "activated_at": "2026-04-19T10:30:00+09:00",
        },
    )

    assert response.status_code == 200
    assert len(learning_service.events) == 1
    assert learning_service.events[0].event_name == "promotion_review_completed"
    assert learning_service.events[0].market == "KRW-XRP"
    assert learning_service.events[0].mode == "demo"
    assert learning_service.events[0].payload == {
        "demo_days": 16,
        "total_trades": 132,
        "profit_factor": 1.31,
        "max_drawdown": 0.051,
        "stoploss_failures": 0,
        "approval_granted": True,
        "approved_by": "manual_review",
        "activated_at": "2026-04-19T10:30:00+09:00",
        "evaluation_status": "READY_FOR_REVIEW",
        "approved": False,
        "rejection_reasons": [],
        "live_enabled": True,
        "safe_mode_entry": True,
        "reason_code": None,
    }


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


def test_promotion_history_endpoint_returns_empty_before_review(monkeypatch) -> None:
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

    response = client.get("/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "history": [],
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


def test_promotion_history_endpoint_returns_accumulated_reviews(monkeypatch) -> None:
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

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
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
            "activated_at": "2026-04-19T11:00:00+09:00",
        },
    )

    response = client.get("/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "evaluation_status": "NOT_READY",
                "approved": False,
                "rejection_reasons": [
                    "DEMO_DAYS_BELOW_THRESHOLD",
                    "TRADE_COUNT_BELOW_THRESHOLD",
                    "PROFIT_FACTOR_BELOW_THRESHOLD",
                    "MAX_DRAWDOWN_ABOVE_THRESHOLD",
                    "STOPLOSS_FAILURES_ABOVE_THRESHOLD",
                ],
                "live_enabled": False,
                "safe_mode_entry": False,
                "reason_code": "PROMOTION_NOT_READY",
                "reviewed_at": "2026-04-19T10:00:00+09:00",
            },
            {
                "market": "KRW-XRP",
                "evaluation_status": "READY_FOR_REVIEW",
                "approved": False,
                "rejection_reasons": [],
                "live_enabled": True,
                "safe_mode_entry": True,
                "reason_code": None,
                "reviewed_at": "2026-04-19T11:00:00+09:00",
            },
        ],
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


def test_dashboard_promotion_returns_empty_before_review(monkeypatch) -> None:
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

    response = client.get("/dashboard/promotion")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "promotion": None,
    }


def test_dashboard_promotion_history_returns_empty_before_review(monkeypatch) -> None:
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

    response = client.get("/dashboard/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "history": [],
    }


def test_dashboard_promotion_returns_last_review_payload(monkeypatch) -> None:
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

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
    )

    response = client.get("/dashboard/promotion")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "promotion": {
            "market": "KRW-XRP",
            "ready_for_review": False,
            "evaluation_status": "NOT_READY",
            "live_enabled": False,
            "safe_mode_entry": False,
            "reason_code": "PROMOTION_NOT_READY",
            "blocking_reasons": [
                "DEMO_DAYS_BELOW_THRESHOLD",
                "TRADE_COUNT_BELOW_THRESHOLD",
                "PROFIT_FACTOR_BELOW_THRESHOLD",
                "MAX_DRAWDOWN_ABOVE_THRESHOLD",
                "STOPLOSS_FAILURES_ABOVE_THRESHOLD",
            ],
            "reviewed_at": "2026-04-19T10:00:00+09:00",
        },
    }


def test_dashboard_promotion_history_returns_compact_review_timeline(monkeypatch) -> None:
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

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
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
            "activated_at": "2026-04-19T11:00:00+09:00",
        },
    )

    response = client.get("/dashboard/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "reviewed_at": "2026-04-19T10:00:00+09:00",
                "evaluation_status": "NOT_READY",
                "ready_for_review": False,
                "live_enabled": False,
                "reason_code": "PROMOTION_NOT_READY",
            },
            {
                "market": "KRW-XRP",
                "reviewed_at": "2026-04-19T11:00:00+09:00",
                "evaluation_status": "READY_FOR_REVIEW",
                "ready_for_review": True,
                "live_enabled": True,
                "reason_code": None,
            },
        ],
    }
