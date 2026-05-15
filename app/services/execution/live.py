from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.execution.demo import OrderIntent
from app.services.execution.rules import UpbitOrderRules


class UpbitLiveOrderGateway:
    """Map internal order fields to Upbit live order endpoints."""

    SIDE_MAP = {
        "buy": "bid",
        "sell": "ask",
    }

    def __init__(self, *, rest_client: Any) -> None:
        self._rest_client = rest_client

    def test_order(
        self,
        *,
        market: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str,
    ) -> dict[str, object]:
        return self._rest_client.post(
            "/v1/orders/test",
            json_payload=self._payload(
                market=market,
                side=side,
                price=price,
                quantity=quantity,
                order_type=order_type,
            ),
        )

    def place_order(
        self,
        *,
        market: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str,
    ) -> dict[str, object]:
        return self._rest_client.post(
            "/v1/orders",
            json_payload=self._payload(
                market=market,
                side=side,
                price=price,
                quantity=quantity,
                order_type=order_type,
            ),
        )

    def get_order(self, *, order_id: str) -> dict[str, object]:
        return self._rest_client.get(
            "/v1/order",
            params={"uuid": order_id},
        )

    def _payload(
        self,
        *,
        market: str,
        side: str,
        price: float,
        quantity: float,
        order_type: str,
    ) -> dict[str, str]:
        upbit_side = self.SIDE_MAP[side]
        if order_type == "market" and side == "buy":
            return {
                "market": market,
                "side": upbit_side,
                "price": str(round(price * quantity, 8)),
                "ord_type": "price",
            }
        if order_type == "market" and side == "sell":
            return {
                "market": market,
                "side": upbit_side,
                "volume": str(quantity),
                "ord_type": "market",
            }

        return {
            "market": market,
            "side": upbit_side,
            "price": str(price),
            "volume": str(quantity),
            "ord_type": order_type,
        }


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
        order_rules: UpbitOrderRules | None = None,
    ) -> None:
        self._live_order_gateway = live_order_gateway
        self._trading_mode = trading_mode
        self._safe_mode = safe_mode
        self._hard_stop = hard_stop
        self._order_rules = order_rules or UpbitOrderRules()

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
        if not self._order_rules.is_allowed(
            market=intent.market,
            price=intent.price,
            quantity=intent.quantity,
        ):
            return LiveExecutionResult(
                accepted=False,
                order_id=None,
                status="blocked",
                blocked_reason="MIN_ORDER_AMOUNT",
            )

        precheck = self._precheck(intent)
        if precheck is not None:
            return precheck

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

    def _precheck(self, intent: OrderIntent) -> LiveExecutionResult | None:
        test_order = getattr(self._live_order_gateway, "test_order", None)
        if test_order is None:
            return None

        response = test_order(
            market=intent.market,
            side=intent.side,
            price=intent.price,
            quantity=intent.quantity,
            order_type=intent.order_type,
        )
        if response.get("ok") is True:
            return None

        return LiveExecutionResult(
            accepted=False,
            order_id=None,
            status="blocked",
            blocked_reason=str(response.get("reason", "LIVE_PRECHECK_FAILED")),
        )

    def order_status(self, order_id: str) -> dict[str, object]:
        get_order = getattr(self._live_order_gateway, "get_order", None)
        if get_order is None:
            return {
                "order_id": order_id,
                "state": "unknown",
                "blocked_reason": "LIVE_ORDER_STATUS_UNAVAILABLE",
            }
        response = get_order(order_id=order_id)
        return {
            "order_id": str(response.get("uuid", order_id)),
            "state": str(response.get("state", "unknown")),
            "market": response.get("market"),
            "side": response.get("side"),
            "price": response.get("price"),
            "volume": response.get("volume"),
            "remaining_volume": response.get("remaining_volume"),
            "executed_volume": response.get("executed_volume"),
            "paid_fee": response.get("paid_fee"),
        }
