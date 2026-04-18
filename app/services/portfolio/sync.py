from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PortfolioSyncError(RuntimeError):
    """Raised when the initial portfolio synchronization fails."""


@dataclass(frozen=True)
class PortfolioState:
    cash_balance: float
    asset_currency: str
    asset_balance: float
    avg_buy_price: float


class PortfolioSyncService:
    """Load the current KRW cash and target coin position from Upbit."""

    def __init__(self, upbit_client: Any, trade_coin: str) -> None:
        self._upbit_client = upbit_client
        self._trade_coin = trade_coin

    def sync(self) -> PortfolioState:
        payload = self._upbit_client.get("/v1/accounts")
        if not isinstance(payload, list):
            raise PortfolioSyncError("Portfolio sync response must be a list")

        cash_entry = self._find_currency(payload, "KRW")
        if cash_entry is None:
            raise PortfolioSyncError("KRW balance is required before trading can start")

        asset_entry = self._find_currency(payload, self._trade_coin)
        return PortfolioState(
            cash_balance=float(cash_entry.get("balance", 0.0)),
            asset_currency=self._trade_coin,
            asset_balance=float((asset_entry or {}).get("balance", 0.0)),
            avg_buy_price=float((asset_entry or {}).get("avg_buy_price", 0.0)),
        )

    @staticmethod
    def _find_currency(payload: list[dict[str, Any]], currency: str) -> dict[str, Any] | None:
        for item in payload:
            if item.get("currency") == currency:
                return item
        return None
