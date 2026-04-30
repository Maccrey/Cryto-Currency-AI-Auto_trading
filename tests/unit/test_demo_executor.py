from __future__ import annotations

from app.services.execution.demo import DemoExecutor, FillResult, OrderIntent


class ForbiddenLiveOrderGateway:
    def place_order(self, *args, **kwargs):
        raise AssertionError("demo executor must not call live order gateway")


def test_demo_executor_returns_virtual_fill_without_live_order_call() -> None:
    executor = DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway())
    intent = OrderIntent(
        market="KRW-XRP",
        side="buy",
        price=820.0,
        quantity=120.5,
        order_type="limit",
        is_stop_loss=False,
    )

    fill = executor.execute(intent)

    assert fill == FillResult(
        market="KRW-XRP",
        side="buy",
        filled_price=820.0,
        filled_quantity=120.5,
        fee=49.41,
        status="filled",
        mode="demo",
        is_virtual=True,
        is_stop_loss=False,
    )


def test_demo_executor_preserves_stop_loss_flag_in_virtual_fill() -> None:
    executor = DemoExecutor(live_order_gateway=ForbiddenLiveOrderGateway())
    intent = OrderIntent(
        market="KRW-XRP",
        side="sell",
        price=805.0,
        quantity=190.5,
        order_type="market",
        is_stop_loss=True,
    )

    fill = executor.execute(intent)

    assert fill.mode == "demo"
    assert fill.is_virtual is True
    assert fill.is_stop_loss is True


def test_demo_executor_accepts_fee_rate() -> None:
    executor = DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        fee_rate=0.001,
    )

    fill = executor.execute(
        OrderIntent(
            market="KRW-XRP",
            side="buy",
            price=1000.0,
            quantity=10.0,
            order_type="market",
            is_stop_loss=False,
        ),
    )

    assert fill.fee == 10.0
