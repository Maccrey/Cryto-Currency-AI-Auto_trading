from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ExternalMarketContextConfig:
    enabled: bool = True
    onchain_source: str = "manual"
    onchain_state: str = "neutral"
    onchain_active_addresses_change_pct: float = 0.0
    onchain_exchange_netflow_state: str = "neutral"
    etf_source: str = "manual"
    etf_state: str = "neutral"
    etf_flow_usd: float = 0.0


class ExternalMarketContextService:
    """Build a stable on-chain and ETF context snapshot for learning and dashboard use."""

    ETF_SUPPORTED_COINS = {"BTC", "ETH"}

    def __init__(self, *, config: ExternalMarketContextConfig | None = None) -> None:
        self._config = config or ExternalMarketContextConfig()

    def snapshot(self, *, market: str, trade_coin: str) -> dict[str, object]:
        coin = trade_coin.upper()
        if not self._config.enabled:
            return {
                "enabled": False,
                "market": market,
                "trade_coin": coin,
                "onchain": {"state": "disabled"},
                "etf": {"state": "disabled"},
                "learning_weight": 1.0,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        etf_state = self._config.etf_state if coin in self.ETF_SUPPORTED_COINS else "not_applicable"
        context = {
            "enabled": True,
            "market": market,
            "trade_coin": coin,
            "onchain": {
                "source": self._config.onchain_source,
                "state": self._config.onchain_state,
                "active_addresses_change_pct": self._config.onchain_active_addresses_change_pct,
                "exchange_netflow_state": self._config.onchain_exchange_netflow_state,
            },
            "etf": {
                "source": self._config.etf_source,
                "state": etf_state,
                "flow_usd": self._config.etf_flow_usd if coin in self.ETF_SUPPORTED_COINS else 0.0,
            },
            "learning_weight": self._learning_weight(etf_state=etf_state),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        return context

    def _learning_weight(self, *, etf_state: str) -> float:
        weight = 1.0
        if self._config.onchain_state == "bullish":
            weight += 0.08
        if self._config.onchain_state == "bearish":
            weight -= 0.08
        if self._config.onchain_exchange_netflow_state == "outflow":
            weight += 0.04
        if self._config.onchain_exchange_netflow_state == "inflow":
            weight -= 0.04
        if etf_state == "inflow":
            weight += 0.08
        if etf_state == "outflow":
            weight -= 0.08
        return round(max(min(weight, 1.25), 0.75), 3)
