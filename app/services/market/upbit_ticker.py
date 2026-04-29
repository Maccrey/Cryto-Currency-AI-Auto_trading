from __future__ import annotations

from typing import Any

import httpx


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
        response = self._client.get("/v1/ticker", params={"markets": market})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            return None
        first: Any = payload[0]
        if not isinstance(first, dict) or first.get("trade_price") is None:
            return None
        return float(first["trade_price"])

    def close(self) -> None:
        self._client.close()
