from app.services.dashboard.executions import DashboardExecutionsService
from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger


def test_dashboard_executions_facade_returns_empty_without_records() -> None:
    facade = DashboardExecutionsFacade(
        execution_ledger=ExecutionLedger(),
        dashboard_executions_service=DashboardExecutionsService(),
    )

    payload = facade.build_history_response()

    assert payload == {
        "status": "empty",
        "history": [],
    }


def test_dashboard_executions_facade_returns_recent_execution_history() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=100.0,
            fee=34.12,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=805.0,
            filled_quantity=100.0,
            fee=33.5,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=True,
        ),
        reason_code="STOP_LOSS_PRICE_HIT",
    )
    facade = DashboardExecutionsFacade(
        execution_ledger=ledger,
        dashboard_executions_service=DashboardExecutionsService(),
    )

    payload = facade.build_history_response(limit=1)

    assert payload == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "side": "sell",
                "severity": "critical",
                "state_message": "손절 매도 체결이 완료되었습니다.",
                "filled_price": 805.0,
                "filled_quantity": 100.0,
                "fee": 33.5,
                "status": "filled",
                "mode": "demo",
                "is_virtual": True,
                "is_stop_loss": True,
                "reason_code": "STOP_LOSS_PRICE_HIT",
            },
        ],
    }
