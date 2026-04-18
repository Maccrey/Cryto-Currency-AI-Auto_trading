from __future__ import annotations

from app.services.execution.demo import OrderIntent
from app.services.execution.factory import ExecutionFactory
from app.services.execution.live import LiveExecutor, LiveExecutionResult


class StubLiveOrderGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def place_order(
        self,
        *,
        market: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "market": market,
                "side": side,
                "price": price,
                "quantity": quantity,
                "order_type": order_type,
            },
        )
        return {
            "uuid": "live-order-1",
            "market": market,
            "side": side,
            "price": price,
            "volume": quantity,
            "ord_type": order_type,
            "state": "wait",
        }


def test_live_executor_places_order_only_in_live_mode() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
    )
    intent = OrderIntent(
        market="KRW-XRP",
        side="buy",
        price=820.0,
        quantity=120.5,
        order_type="limit",
        is_stop_loss=False,
    )

    result = executor.execute(intent)

    assert gateway.calls == [
        {
            "market": "KRW-XRP",
            "side": "buy",
            "price": 820.0,
            "quantity": 120.5,
            "order_type": "limit",
        }
    ]
    assert result == LiveExecutionResult(
        accepted=True,
        order_id="live-order-1",
        status="wait",
        blocked_reason=None,
    )


def test_live_executor_blocks_orders_in_safe_mode() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=True,
    )

    result = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="sell",
            price=805.0,
            quantity=190.5,
            order_type="market",
            is_stop_loss=True,
        ),
    )

    assert gateway.calls == []
    assert result == LiveExecutionResult(
        accepted=False,
        order_id=None,
        status="blocked",
        blocked_reason="SAFE_MODE_ACTIVE",
    )


def test_execution_factory_returns_executor_by_mode() -> None:
    gateway = StubLiveOrderGateway()
    factory = ExecutionFactory(live_order_gateway=gateway)

    demo_executor = factory.create(trading_mode="demo", safe_mode=False)
    live_executor = factory.create(trading_mode="live", safe_mode=False)

    assert demo_executor.__class__.__name__ == "DemoExecutor"
    assert live_executor.__class__.__name__ == "LiveExecutor"

