from __future__ import annotations

import base64
import hashlib
import hmac
import json
from uuid import uuid4

import httpx


class CoinoneAPIError(RuntimeError):
    pass


class CoinoneRestClient:
    def __init__(self, *, access_token: str = "", secret_key: str = "",
                 base_url: str = "https://api.coinone.co.kr", transport=None, timeout=5.0):
        self._access_token = access_token
        self._secret_key = secret_key
        self._client = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)

    @staticmethod
    def _decode(response):
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("result") != "success" or str(payload.get("error_code")) != "0":
            code = payload.get("error_code", "invalid_response") if isinstance(payload, dict) else "invalid_response"
            raise CoinoneAPIError(f"Coinone API error: {code}")
        return payload

    def public_get(self, path, *, params=None):
        return self._decode(self._client.get(path, params=params))

    def post(self, path, *, json_payload=None):
        if not self._access_token or not self._secret_key:
            raise CoinoneAPIError("Coinone credentials missing")
        payload = {**(json_payload or {}), "access_token": self._access_token, "nonce": str(uuid4())}
        encoded = base64.b64encode(json.dumps(payload).encode())
        signature = hmac.new(self._secret_key.encode(), encoded, hashlib.sha512).hexdigest()
        return self._decode(self._client.post(path, content=encoded, headers={
            "Content-Type": "application/json", "X-COINONE-PAYLOAD": encoded.decode(),
            "X-COINONE-SIGNATURE": signature,
        }))

    def get(self, path, *, params=None):
        """Normalize account/recovery data to the existing portfolio interface."""
        if path == "/v1/accounts":
            rows = self.post("/v2.1/account/balance/all")["balances"]
            return [{"currency": row["currency"], "balance": row["available"],
                     "locked": row["limit"], "avg_buy_price": row["average_price"]} for row in rows]
        if path == "/v1/orders/open":
            quote, coin = params["market"].split("-")
            rows = self.post("/v2.1/order/active_orders", json_payload={
                "quote_currency": quote, "target_currency": coin,
            })["active_orders"]
            return [{"uuid": row["order_id"], "market": params["market"]} for row in rows]
        raise ValueError(f"Unsupported account operation: {path}")

    def close(self):
        self._client.close()
