from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.learning.service import LearningEvent

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

    FEE_RATE = 0.0005

    def __init__(
        self,
        *,
        live_order_gateway: Any,
        learning_service=None,
        fee_rate: float = FEE_RATE,
    ) -> None:
        self._live_order_gateway = live_order_gateway
        self._learning_service = learning_service
        self._fee_rate = fee_rate

    def execute(self, intent: OrderIntent) -> FillResult:
        notional = intent.price * intent.quantity
        fee = round(notional * self._fee_rate, 2)
        fill = FillResult(
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
        if self._learning_service is not None:
            self._learning_service.record(
                LearningEvent(
                    event_name="fill_result",
                    market=fill.market,
                    mode=fill.mode,
                    payload={
                        "side": fill.side,
                        "filled_price": fill.filled_price,
                        "filled_quantity": fill.filled_quantity,
                        "fee": fill.fee,
                        "is_stop_loss": fill.is_stop_loss,
                    },
                ),
            )
        return fill
