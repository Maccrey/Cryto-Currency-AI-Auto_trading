from types import SimpleNamespace

import pytest

from app.services.execution.demo import FillResult, OrderIntent
from app.services.execution.live import LiveExecutor, UpbitLiveOrderGateway
from app.services.execution.ledger import ExecutionLedger
from app.services.position.exit import PositionExitService
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import StopLossInjector
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService


class Gateway:
    def __init__(self):
        self.calls = []
        self.state = "wait"
        self.quantity = "8"

    def place_order(self, **kwargs):
        self.calls.append(kwargs)
        return {"uuid": str(len(self.calls)), "state": "wait"}

    def get_order(self, *, order_id):
        return {"uuid": order_id, "state": self.state, "executed_volume": self.quantity,
                "paid_fee": "8", "trades": [{"price": "2000", "volume": self.quantity, "funds": str(2000 * float(self.quantity))}]}


def test_round_trip_uses_exchange_fills_and_preserves_pending_position():
    gateway = Gateway()
    executor = LiveExecutor(live_order_gateway=gateway, trading_mode="live", safe_mode=False)
    store, ledger = CurrentPositionStore(), ExecutionLedger()
    trades = TradeExecutionService(executor=executor, market="KRW-XRP")
    post = PostFillService(stop_loss_injector=StopLossInjector(stop_loss_by_signal={"medium": .03},
                           validation_window_sec=180, min_expected_return_pct=.004),
                           position_store=store, execution_ledger=ledger)
    decision = SimpleNamespace(sizing=SimpleNamespace(allowed=True, buy_amount=20000, buy_quantity=10, order_side="buy"),
                               signal=SimpleNamespace(level="medium", score=.6))
    submitted = trades.execute(decision)
    post.process(submitted)
    assert store.get() is None
    assert trades.resolve_order("1").status == "wait"
    gateway.state = "cancel"  # Partial market buy followed by canceled remainder.
    filled = trades.resolve_order("1")
    assert isinstance(filled.execution, FillResult)
    post.process(filled)
    trades.acknowledge_order("1")
    assert store.get().quantity == 8  # Never the requested 10.
    exits = PositionExitService(position_store=store, executor=executor, trading_mode="live",
                                hard_stop_monitor=HardStopMonitor(), post_entry_validator=PostEntryValidator(), execution_ledger=ledger)
    args = dict(current_price=1900, elapsed_sec=60, momentum_score=-.5, orderbook_imbalance=-.3)
    assert exits.evaluate_and_execute(**args)["status"] == "pending"
    assert store.get().quantity == 8
    gateway.state = "wait"
    assert exits.evaluate_and_execute(**args)["status"] == "pending"
    assert len(gateway.calls) == 2
    gateway.state, gateway.quantity = "cancel", "3"
    result = exits.evaluate_and_execute(**args)
    assert result["execution"]["filled_quantity"] == 3
    assert store.get().quantity == 5
    assert len(ledger.list_records()) == 2
    assert ledger.list_records()[1].fill.fee == 8


def test_uncertain_submission_and_restart_cannot_duplicate_order(tmp_path):
    class TimeoutGateway(Gateway):
        def place_order(self, **kwargs):
            self.calls.append(kwargs)
            raise TimeoutError("response lost")
    gateway = TimeoutGateway()
    path = tmp_path / "pending.json"
    executor = LiveExecutor(live_order_gateway=gateway, trading_mode="live", safe_mode=False, journal_path=path)
    intent = OrderIntent("KRW-XRP", "buy", 2000, 10, "market", False)
    with pytest.raises(TimeoutError):
        executor.execute(intent)
    assert not executor.execute(intent).accepted
    restarted = LiveExecutor(live_order_gateway=gateway, trading_mode="live", safe_mode=False, journal_path=path)
    assert not restarted.execute(intent).accepted
    assert len(gateway.calls) == 1


def test_upbit_dry_run_order_object_is_success():
    client = SimpleNamespace(post=lambda *args, **kwargs: {"uuid": "test-uuid", "state": "wait"})
    assert UpbitLiveOrderGateway(rest_client=client).test_order(market="KRW-XRP", side="buy", price=2000, quantity=10, order_type="market") == {"ok": True}


def test_missing_fill_data_keeps_order_pending():
    gateway = Gateway()
    executor = LiveExecutor(live_order_gateway=gateway, trading_mode="live", safe_mode=False)
    intent = OrderIntent("KRW-XRP", "buy", 2000, 10, "market", False)
    executor.execute(intent)
    gateway.get_order = lambda **kwargs: {"state": "done"}
    with pytest.raises(ValueError, match="volume missing"):
        executor.resolve_order("1")
    assert not executor.execute(intent).accepted
