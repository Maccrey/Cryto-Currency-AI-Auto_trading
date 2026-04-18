from __future__ import annotations

from typing import Any


class OpenOrderReconcileError(RuntimeError):
    """Raised when open-order reconciliation cannot complete safely."""


class OpenOrderReconciler:
    """Load open orders for the target market during boot reconciliation."""

    def __init__(self, *, upbit_client: Any, trade_market: str) -> None:
        self._upbit_client = upbit_client
        self._trade_market = trade_market

    def reconcile(self) -> dict[str, object]:
        payload = self._upbit_client.get(
            "/v1/orders/open",
            params={
                "market": self._trade_market,
                "states[]": ["wait", "watch"],
            },
        )
        if not isinstance(payload, list):
            raise OpenOrderReconcileError("Open order reconcile response must be a list")

        return {
            "open_order_count": len(payload),
            "markets": sorted({str(item.get("market", self._trade_market)) for item in payload}),
            "order_ids": [str(item.get("uuid")) for item in payload],
            "status": "reconciled",
        }

