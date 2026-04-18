from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OrderIntent:
    market: str
    side: str
    price: float
    quantity: float
    order_type: str
    is_stop_loss: bool


@dataclass(frozen=True)
class FillResult:
    market: str
    side: str
    filled_price: float
    filled_quantity: float
    fee: float
    status: str
    mode: str
    is_virtual: bool
    is_stop_loss: bool


class DemoExecutor:
    """Simulate fills locally without touching any live trading gateway."""

    FEE_RATE = 0.00041605

    def __init__(self, *, live_order_gateway: Any) -> None:
        self._live_order_gateway = live_order_gateway

    def execute(self, intent: OrderIntent) -> FillResult:
        notional = intent.price * intent.quantity
        fee = round(notional * self.FEE_RATE, 2)
        return FillResult(
            market=intent.market,
            side=intent.side,
            filled_price=intent.price,
            filled_quantity=intent.quantity,
            fee=fee,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=intent.is_stop_loss,
        )
