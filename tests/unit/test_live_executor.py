from __future__ import annotations

from app.services.execution.demo import OrderIntent
from app.services.execution.factory import ExecutionFactory
from app.services.execution.interface import ExecutionExecutor
from app.services.execution.live import LiveExecutor, LiveExecutionResult, UpbitLiveOrderGateway


class StubLiveOrderGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.precheck_calls: list[dict[str, object]] = []

    def test_order(
        self,
        *,
        market: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str,
    ) -> dict[str, object]:
        self.precheck_calls.append(
            {
                "market": market,
                "side": side,
                "price": price,
                "quantity": quantity,
                "order_type": order_type,
            },
        )
        return {"ok": True}

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


class StubLearningService:
    def __init__(self) -> None:
        self.events: list[str] = []

    def record(self, event) -> None:
        self.events.append(event.event_name)


def test_live_executor_places_order_only_in_live_mode() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
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
    assert gateway.precheck_calls == gateway.calls
    assert result == LiveExecutionResult(
        accepted=True,
        order_id="live-order-1",
        status="wait",
        blocked_reason=None,
    )


def test_live_executor_blocks_order_when_precheck_fails() -> None:
    class FailingPrecheckGateway(StubLiveOrderGateway):
        def test_order(self, **kwargs) -> dict[str, object]:
            self.precheck_calls.append(kwargs)
            return {"ok": False, "reason": "INSUFFICIENT_BALANCE"}

    gateway = FailingPrecheckGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
    )

    result = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=820.0,
            quantity=120.5,
            order_type="limit",
            is_stop_loss=False,
        ),
    )

    assert gateway.calls == []
    assert result == LiveExecutionResult(
        accepted=False,
        order_id=None,
        status="blocked",
        blocked_reason="INSUFFICIENT_BALANCE",
    )


def test_upbit_live_order_gateway_calls_test_and_order_endpoints() -> None:
    class RestClientStub:
        def __init__(self) -> None:
            self.calls = []

        def post(self, path, *, json_payload):
            self.calls.append((path, json_payload))
            if path == "/v1/orders/test":
                return {"ok": True}
            return {"uuid": "live-order-1", "state": "wait"}

    rest_client = RestClientStub()
    gateway = UpbitLiveOrderGateway(rest_client=rest_client)

    precheck = gateway.test_order(
        market="KRW-XRP",
        side="buy",
        price=820.0,
        quantity=120.5,
        order_type="limit",
    )
    order = gateway.place_order(
        market="KRW-XRP",
        side="sell",
        price=805.0,
        quantity=10.0,
        order_type="market",
    )

    assert precheck == {"ok": True}
    assert order == {"uuid": "live-order-1", "state": "wait"}
    assert rest_client.calls == [
        (
            "/v1/orders/test",
            {
                "market": "KRW-XRP",
                "side": "bid",
                "price": "820.0",
                "volume": "120.5",
                "ord_type": "limit",
            },
        ),
        (
            "/v1/orders",
            {
                "market": "KRW-XRP",
                "side": "ask",
                "volume": "10.0",
                "ord_type": "market",
            },
        ),
    ]


def test_upbit_live_order_gateway_maps_market_buy_to_price_order() -> None:
    class RestClientStub:
        def __init__(self) -> None:
            self.calls = []

        def post(self, path, *, json_payload):
            self.calls.append((path, json_payload))
            return {"ok": True}

    rest_client = RestClientStub()
    gateway = UpbitLiveOrderGateway(rest_client=rest_client)

    gateway.place_order(
        market="KRW-XRP",
        side="buy",
        price=820.0,
        quantity=120.5,
        order_type="market",
    )

    assert rest_client.calls == [
        (
            "/v1/orders",
            {
                "market": "KRW-XRP",
                "side": "bid",
                "price": "98810.0",
                "ord_type": "price",
            },
        )
    ]


def test_live_executor_blocks_orders_in_safe_mode() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=True,
        hard_stop=False,
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


def test_live_executor_blocks_orders_during_hard_stop() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=True,
    )

    result = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=812.0,
            quantity=100.0,
            order_type="limit",
            is_stop_loss=False,
        ),
    )

    assert gateway.calls == []
    assert result == LiveExecutionResult(
        accepted=False,
        order_id=None,
        status="blocked",
        blocked_reason="HARD_STOP_ACTIVE",
    )


def test_live_executor_blocks_krw_orders_below_upbit_minimum_amount() -> None:
    gateway = StubLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
    )

    result = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=800.0,
            quantity=5.0,
            order_type="market",
            is_stop_loss=False,
        ),
    )

    assert gateway.precheck_calls == []
    assert gateway.calls == []
    assert result == LiveExecutionResult(
        accepted=False,
        order_id=None,
        status="blocked",
        blocked_reason="MIN_ORDER_AMOUNT",
    )


def test_execution_factory_returns_executor_by_mode() -> None:
    gateway = StubLiveOrderGateway()
    learning_service = StubLearningService()
    factory = ExecutionFactory(
        live_order_gateway=gateway,
        learning_service=learning_service,
    )

    demo_executor = factory.create(trading_mode="demo", safe_mode=False, hard_stop=False)
    live_executor = factory.create(trading_mode="live", safe_mode=False, hard_stop=False)

    assert demo_executor.__class__.__name__ == "DemoExecutor"
    assert live_executor.__class__.__name__ == "LiveExecutor"
    assert isinstance(demo_executor, ExecutionExecutor)
    assert isinstance(live_executor, ExecutionExecutor)
    demo_executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=820.0,
            quantity=100.0,
            order_type="limit",
            is_stop_loss=False,
        ),
    )
    assert learning_service.events == ["fill_result"]
