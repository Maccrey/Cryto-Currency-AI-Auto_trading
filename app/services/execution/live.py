from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from threading import RLock
from typing import Any

from app.services.execution.demo import FillResult, OrderIntent
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
        response = self._rest_client.post(
            "/v1/orders/test",
            json_payload=self._payload(
                market=market,
                side=side,
                price=price,
                quantity=quantity,
                order_type=order_type,
            ),
        )
        if response.get("uuid") and response.get("state") and not response.get("error"):
            return {"ok": True}
        return response

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
        journal_path: Path | None = None,
    ) -> None:
        self._live_order_gateway = live_order_gateway
        self._trading_mode = trading_mode
        self._safe_mode = safe_mode
        self._hard_stop = hard_stop
        self._order_rules = order_rules or UpbitOrderRules()
        self._pending: tuple[str, OrderIntent] | None = None
        self._lock = RLock()
        self._journal_path = journal_path
        self._uncertain = bool(journal_path and journal_path.exists() and json.loads(journal_path.read_text()).get("pending"))

    def execute(self, intent: OrderIntent) -> LiveExecutionResult:
        with self._lock:
            return self._execute(intent)

    def _execute(self, intent: OrderIntent) -> LiveExecutionResult:
        if self._uncertain or self._pending is not None:
            return LiveExecutionResult(False, None, "blocked", "LIVE_ORDER_RECONCILIATION_REQUIRED")
        if intent.side not in {"buy", "sell"} or not all(math.isfinite(v) and v > 0 for v in (intent.price, intent.quantity)):
            return LiveExecutionResult(False, None, "blocked", "INVALID_ORDER")
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

        # Persist before sending: a timeout must never cause a duplicate order.
        self._write_journal({"pending": True, "intent": asdict(intent), "order_id": None})
        self._uncertain = True
        response = self._live_order_gateway.place_order(
            market=intent.market,
            side=intent.side,
            price=intent.price,
            quantity=intent.quantity,
            order_type=intent.order_type,
        )
        self._pending = (str(response["uuid"]), intent)
        self._write_journal({"pending": True, "intent": asdict(intent), "order_id": str(response["uuid"])})
        self._uncertain = False
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
            "average_price": response.get("average_price"),
            "trades": response.get("trades"),
        }

    def resolve_order(self, order_id: str) -> FillResult | LiveExecutionResult:
        if self._pending is None or self._pending[0] != order_id:
            return LiveExecutionResult(False, order_id, "blocked", "LIVE_ORDER_RECONCILIATION_REQUIRED")
        status = self.order_status(order_id)
        if status["state"] not in {"done", "cancel"}:
            return LiveExecutionResult(True, order_id, "wait", None)
        if status.get("executed_volume") is None:
            raise ValueError("Exchange executed volume missing")
        quantity = float(status["executed_volume"])
        if quantity <= 0:
            if status["state"] != "cancel" or quantity < 0:
                raise ValueError("Invalid terminal fill quantity")
            return LiveExecutionResult(False, order_id, "cancel", "ORDER_CANCELED_UNFILLED")
        trades = status.get("trades") or []
        funds = sum(float(t.get("funds") or float(t["price"]) * float(t["volume"])) for t in trades)
        price = funds / quantity if trades else float(status.get("average_price") or 0)
        fee = float(status["paid_fee"])
        if not all(math.isfinite(v) for v in (quantity, price, fee)) or price <= 0 or fee < 0:
            raise ValueError("Invalid exchange fill data")
        intent = self._pending[1]
        return FillResult(intent.market, intent.side, price, quantity, fee, "filled", "live", False, intent.is_stop_loss)

    def recovery_required(self) -> bool:
        return self._uncertain

    def acknowledge_order(self, order_id: str) -> None:
        if self._pending is not None and self._pending[0] == order_id:
            self._write_journal({"pending": False})
            self._pending = None

    def _write_journal(self, value: dict) -> None:
        if self._journal_path is not None:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._journal_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(value), encoding="utf-8")
            temporary.replace(self._journal_path)
