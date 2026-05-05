from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ExternalMarketContextConfig:
    enabled: bool = True
    onchain_source: str = "manual"
    onchain_url: str = ""
    onchain_state: str = "neutral"
    onchain_active_addresses_change_pct: float = 0.0
    onchain_exchange_netflow_state: str = "neutral"
    etf_source: str = "manual"
    etf_url: str = ""
    etf_state: str = "neutral"
    etf_flow_usd: float = 0.0


class ExternalMarketContextProvider(Protocol):
    def fetch(self, *, market: str, trade_coin: str) -> dict[str, dict[str, object]]:
        """Fetch partial external context sections keyed by onchain/etf."""


class HttpExternalMarketContextProvider:
    """Fetch optional on-chain and ETF context JSON from configured HTTP endpoints."""

    def __init__(
        self,
        *,
        onchain_url: str = "",
        etf_url: str = "",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 3.0,
    ) -> None:
        self._onchain_url = onchain_url
        self._etf_url = etf_url
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def fetch(self, *, market: str, trade_coin: str) -> dict[str, dict[str, object]]:
        payload: dict[str, dict[str, object]] = {}
        errors: dict[str, object] = {}
        if self._onchain_url:
            section, error = self._fetch_optional(self._onchain_url, market=market, trade_coin=trade_coin)
            if error:
                errors["onchain"] = error
            else:
                payload["onchain"] = section
        if self._etf_url:
            section, error = self._fetch_optional(self._etf_url, market=market, trade_coin=trade_coin)
            if error:
                errors["etf"] = error
            else:
                payload["etf"] = section
        if errors:
            payload["_errors"] = errors
        return payload

    def close(self) -> None:
        self._client.close()

    def _fetch_section(self, url: str, *, market: str, trade_coin: str) -> dict[str, object]:
        response = self._client.get(url, params={"market": market, "coin": trade_coin.upper()})
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            return {}
        section = raw.get("context", raw)
        return section if isinstance(section, dict) else {}

    def _fetch_optional(self, url: str, *, market: str, trade_coin: str) -> tuple[dict[str, object], str]:
        try:
            return self._fetch_section(url, market=market, trade_coin=trade_coin), ""
        except Exception as exc:
            return {}, str(exc)


class ExternalMarketContextService:
    """Build a stable on-chain and ETF context snapshot for learning and dashboard use."""

    ETF_SUPPORTED_COINS = {"BTC", "ETH"}

    def __init__(
        self,
        *,
        config: ExternalMarketContextConfig | None = None,
        provider: ExternalMarketContextProvider | None = None,
    ) -> None:
        self._config = config or ExternalMarketContextConfig()
        self._provider = provider

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
        provider_payload, fetch_errors = self._provider_payload(market=market, trade_coin=coin)
        onchain_payload = provider_payload.get("onchain", {})
        etf_payload = provider_payload.get("etf", {})
        onchain_state = self._string_value(onchain_payload.get("state"), self._config.onchain_state)
        onchain_exchange_netflow_state = self._string_value(
            onchain_payload.get("exchange_netflow_state"),
            self._config.onchain_exchange_netflow_state,
        )
        onchain_active_addresses_change_pct = self._float_value(
            onchain_payload.get("active_addresses_change_pct"),
            self._config.onchain_active_addresses_change_pct,
        )
        configured_etf_state = self._string_value(etf_payload.get("state"), self._config.etf_state)
        etf_state = configured_etf_state if coin in self.ETF_SUPPORTED_COINS else "not_applicable"
        etf_flow_usd = self._float_value(etf_payload.get("flow_usd"), self._config.etf_flow_usd)
        onchain_source = "http" if onchain_payload else self._config.onchain_source
        etf_source = "http" if etf_payload else self._config.etf_source
        context = {
            "enabled": True,
            "market": market,
            "trade_coin": coin,
            "onchain": {
                "source": onchain_source,
                "state": onchain_state,
                "active_addresses_change_pct": onchain_active_addresses_change_pct,
                "exchange_netflow_state": onchain_exchange_netflow_state,
            },
            "etf": {
                "source": etf_source,
                "state": etf_state,
                "flow_usd": etf_flow_usd if coin in self.ETF_SUPPORTED_COINS else 0.0,
            },
            "learning_weight": self._learning_weight(
                onchain_state=onchain_state,
                onchain_exchange_netflow_state=onchain_exchange_netflow_state,
                etf_state=etf_state,
            ),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        for section, error in fetch_errors.items():
            context_section = context.get(section)
            if isinstance(context_section, dict):
                context_section["fetch_error"] = error
        return context

    def _provider_payload(self, *, market: str, trade_coin: str) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
        if self._provider is None:
            return {}, {}
        try:
            payload = self._provider.fetch(market=market, trade_coin=trade_coin)
            raw_errors = payload.pop("_errors", {})
            errors = {
                str(key): str(value)
                for key, value in raw_errors.items()
                if key in {"onchain", "etf"} and value
            } if isinstance(raw_errors, dict) else {}
            return payload, errors
        except Exception as exc:
            return {}, {"onchain": str(exc), "etf": str(exc)}

    def _learning_weight(
        self,
        *,
        onchain_state: str,
        onchain_exchange_netflow_state: str,
        etf_state: str,
    ) -> float:
        weight = 1.0
        if onchain_state == "bullish":
            weight += 0.08
        if onchain_state == "bearish":
            weight -= 0.08
        if onchain_exchange_netflow_state == "outflow":
            weight += 0.04
        if onchain_exchange_netflow_state == "inflow":
            weight -= 0.04
        if etf_state == "inflow":
            weight += 0.08
        if etf_state == "outflow":
            weight -= 0.08
        return round(max(min(weight, 1.25), 0.75), 3)

    @staticmethod
    def _string_value(value: Any, fallback: str) -> str:
        if value is None:
            return fallback
        return str(value).strip() or fallback

    @staticmethod
    def _float_value(value: Any, fallback: float) -> float:
        if value is None or value == "":
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
