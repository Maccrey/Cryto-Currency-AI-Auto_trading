from datetime import date

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


def test_execution_ledger_builds_performance_profile_for_loss_guard() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=1000.0,
            filled_quantity=100.0,
            fee=50.0,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
        signal_level="weak",
        signal_score=0.24,
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=1010.0,
            filled_quantity=50.0,
            fee=25.25,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
        reason_code="TAKE_PROFIT_TARGET_HIT",
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=980.0,
            filled_quantity=50.0,
            fee=24.5,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=True,
        ),
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
    )

    profile = ledger.performance_profile()

    assert profile.buy_count == 1
    assert profile.weak_buy_count == 1
    assert profile.weak_buy_ratio == 1.0
    assert profile.regular_sell_pnl > 0
    assert profile.stop_loss_pnl < 0
    assert profile.stop_loss_to_profit_ratio > 1.0
    assert profile.recent_stop_loss_reason == "STOP_LOSS_MOMENTUM_REVERSAL"


def test_execution_ledger_portfolio_state_ignores_buys_that_exceed_cash() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=187.8049,
            fee=77.0,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=187.8049,
            fee=77.0,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )

    portfolio = ledger.portfolio_state(initial_cash=200000.0, asset_currency="XRP")

    assert portfolio.cash_balance >= 0.0
    assert portfolio.asset_balance == 187.8049


def test_execution_ledger_tracks_consecutive_losing_exits() -> None:
    ledger = ExecutionLedger()
    for buy_price, sell_price in ((1000.0, 980.0), (990.0, 970.0)):
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="buy",
                filled_price=buy_price,
                filled_quantity=10.0,
                fee=5.0,
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
                filled_price=sell_price,
                filled_quantity=10.0,
                fee=4.9,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=True,
            ),
        )

    assert ledger.recent_loss_streak() == 2

    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=970.0,
            filled_quantity=10.0,
            fee=4.85,
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
            filled_price=1000.0,
            filled_quantity=10.0,
            fee=5.0,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )

    assert ledger.recent_loss_streak() == 0


def test_execution_ledger_calculates_daily_realized_pnl_using_cross_day_cost_basis() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP", side="buy", filled_price=1000.0, filled_quantity=1000.0,
            fee=500.0, status="filled", mode="demo", is_virtual=True, is_stop_loss=False,
        ),
        recorded_at="2026-08-01T23:50:00+09:00",
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP", side="sell", filled_price=800.0, filled_quantity=1000.0,
            fee=400.0, status="filled", mode="demo", is_virtual=True, is_stop_loss=True,
        ),
        recorded_at="2026-08-02T00:10:00+09:00",
    )

    assert ledger.realized_pnl_for_date(date(2026, 8, 1)) == 0.0
    assert ledger.realized_pnl_for_date(date(2026, 8, 2)) == -200900.0


def test_execution_ledger_persists_records(tmp_path) -> None:
    storage_path = tmp_path / "execution-ledger.json"
    ledger = ExecutionLedger(storage_path=storage_path)
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=10.0,
            fee=4.1,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )

    restored = ExecutionLedger(storage_path=storage_path)

    assert len(restored.list_records()) == 1
    portfolio = restored.portfolio_state(initial_cash=1_000_000.0, asset_currency="XRP")
    assert portfolio.cash_balance == 991795.9
    assert portfolio.asset_balance == 10.0


def test_execution_ledger_clear_persists_empty_records(tmp_path) -> None:
    storage_path = tmp_path / "execution-ledger.json"
    ledger = ExecutionLedger(storage_path=storage_path)
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=10.0,
            fee=4.1,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    ledger.clear()

    restored = ExecutionLedger(storage_path=storage_path)

    assert restored.list_records() == []
