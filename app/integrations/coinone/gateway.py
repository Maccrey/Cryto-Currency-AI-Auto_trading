from __future__ import annotations

from decimal import Decimal, ROUND_DOWN


class CoinoneLiveOrderGateway:
    def __init__(self, *, rest_client, market: str):
        self._rest_client = rest_client
        self._market = market

    def test_order(self, *, market, side, price, quantity, order_type):
        # Coinone has no dry-run endpoint. Validate against public market rules;
        # the authenticated order endpoint remains authoritative for funds.
        quote, coin = market.split("-")
        spec = self._rest_client.public_get(f"/public/v2/markets/{quote}/{coin}")["markets"][0]
        allowed_status = {"buy": {1, 3}, "sell": {1, 2}}[side]
        if int(spec["maintenance_status"]) != 0 or int(spec["trade_status"]) not in allowed_status:
            return {"ok": False, "reason": "COINONE_MARKET_UNAVAILABLE"}
        if order_type != "market" or order_type not in spec["order_types"]:
            return {"ok": False, "reason": "COINONE_ORDER_TYPE_UNSUPPORTED"}
        amount = Decimal(str(price)) * Decimal(str(quantity))
        if not Decimal(spec["min_order_amount"]) <= amount <= Decimal(spec["max_order_amount"]):
            return {"ok": False, "reason": "COINONE_ORDER_AMOUNT_LIMIT"}
        return {"ok": True}

    def place_order(self, *, market, side, price, quantity, order_type):
        if market != self._market or order_type != "market" or side not in {"buy", "sell"}:
            raise ValueError("Unsupported Coinone order")
        quote, coin = market.split("-")
        payload = {"quote_currency": quote, "target_currency": coin,
                   "side": side.upper(), "type": "MARKET"}
        if side == "buy":
            amount = (Decimal(str(price)) * Decimal(str(quantity))).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
            payload["amount"] = str(amount)
        else:
            payload["qty"] = str(quantity)
        response = self._rest_client.post("/v2.1/order", json_payload=payload)
        return {"uuid": response["order_id"], "state": "wait"}

    def get_order(self, *, order_id):
        quote, coin = self._market.split("-")
        row = self._rest_client.post("/v2.1/order/detail", json_payload={
            "order_id": order_id, "quote_currency": quote, "target_currency": coin,
        })["order"]
        state = row["status"]
        terminal_cancel = {"CANCELED", "CANCELED_NO_ORDER", "CANCELED_LIMIT_PRICE_EXCEED", "CANCELED_UNDER_PRODUCT_UNIT", "NOT_TRIGGERED_CANCELED"}
        normalized = "done" if state == "FILLED" else "cancel" if state in terminal_cancel else "wait"
        return {"uuid": row["order_id"], "state": normalized, "market": self._market,
                "side": "bid" if row["side"] == "BUY" else "ask",
                "average_price": row.get("average_executed_price"),
                "executed_volume": row["executed_qty"], "paid_fee": row["fee"],
                "remaining_volume": row.get("remain_qty", "0"), "volume": row.get("original_qty")}
