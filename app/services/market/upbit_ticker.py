from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class UpbitTickerSnapshot:
    trade_price: float
    signed_change_rate: float | None = None
    acc_trade_volume_24h: float | None = None
    acc_trade_price_24h: float | None = None


class UpbitTickerPriceProvider:
    """Fetch public ticker prices from Upbit when no runtime snapshot exists."""

    def __init__(
        self,
        *,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 3.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
        )

    def get_current_price(self, market: str) -> float | None:
        snapshot = self.get_current_snapshot(market)
        return None if snapshot is None else snapshot.trade_price

    def get_current_snapshot(self, market: str) -> UpbitTickerSnapshot | None:
        response = self._client.get("/v1/ticker", params={"markets": market})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            return None
        first: Any = payload[0]
        if not isinstance(first, dict) or first.get("trade_price") is None:
            return None
        return UpbitTickerSnapshot(
            trade_price=float(first["trade_price"]),
            signed_change_rate=self._optional_float(first.get("signed_change_rate")),
            acc_trade_volume_24h=self._optional_float(first.get("acc_trade_volume_24h")),
            acc_trade_price_24h=self._optional_float(first.get("acc_trade_price_24h")),
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)
