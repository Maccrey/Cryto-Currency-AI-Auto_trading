from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger


def test_execution_ledger_summarizes_buy_sell_and_stop_loss_counts() -> None:
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

    summary = ledger.summarize()

    assert summary.buy_count == 1
    assert summary.sell_count == 1
    assert summary.stop_loss_count == 1
    assert summary.recent_stop_loss_reason == "STOP_LOSS_PRICE_HIT"
    assert summary.realized_pnl < 0.0
