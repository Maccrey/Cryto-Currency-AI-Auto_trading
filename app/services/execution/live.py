from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.execution.demo import OrderIntent


@dataclass(frozen=True)
class LiveExecutionResult:
    accepted: bool
    order_id: str | None
    status: str
    blocked_reason: str | None


class LiveExecutor:
    """Route live orders to the exchange gateway only when trading is permitted."""

    def __init__(
        self,
        *,
        live_order_gateway: Any,
        trading_mode: str,
        safe_mode: bool,
        hard_stop: bool = False,
    ) -> None:
        self._live_order_gateway = live_order_gateway
        self._trading_mode = trading_mode
        self._safe_mode = safe_mode
        self._hard_stop = hard_stop

    def execute(self, intent: OrderIntent) -> LiveExecutionResult:
        if self._trading_mode != "live":
            return LiveExecutionResult(
                accepted=False,
                order_id=None,
                status="blocked",
                blocked_reason="LIVE_MODE_REQUIRED",
            )
        if self._safe_mode:
            return LiveExecutionResult(
                accepted=False,
                order_id=None,
                status="blocked",
                blocked_reason="SAFE_MODE_ACTIVE",
            )
        if self._hard_stop:
            return LiveExecutionResult(
                accepted=False,
                order_id=None,
                status="blocked",
                blocked_reason="HARD_STOP_ACTIVE",
            )

        response = self._live_order_gateway.place_order(
            market=intent.market,
            side=intent.side,
            price=intent.price,
            quantity=intent.quantity,
            order_type=intent.order_type,
        )
        return LiveExecutionResult(
            accepted=True,
            order_id=str(response["uuid"]),
            status=str(response["state"]),
            blocked_reason=None,
        )
