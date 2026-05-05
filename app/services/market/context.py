from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Callable, Protocol

import httpx
import re


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
        cache_ttl_sec: float = 300.0,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._onchain_url = onchain_url
        self._etf_url = etf_url
        self._client = httpx.Client(transport=transport, timeout=timeout)
        self._cache_ttl_sec = max(cache_ttl_sec, 0.0)
        self._monotonic_clock = monotonic_clock
        self._cache: dict[tuple[str, str, str, str], tuple[float, dict[str, object]]] = {}

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
        cache_key = ("context", url, market, trade_coin.upper())
        cached = self._cache.get(cache_key)
        now = self._monotonic_clock()
        if cached and cached[0] > now:
            return dict(cached[1])
        response = self._client.get(url, params={"market": market, "coin": trade_coin.upper()})
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            return {}
        section = raw.get("context", raw)
        result = section if isinstance(section, dict) else {}
        result = dict(result)
        if self._cache_ttl_sec > 0:
            self._cache[cache_key] = (now + self._cache_ttl_sec, result)
        return result

    def _fetch_optional(self, url: str, *, market: str, trade_coin: str) -> tuple[dict[str, object], str]:
        try:
            return self._fetch_section(url, market=market, trade_coin=trade_coin), ""
        except Exception as exc:
            return {}, str(exc)


class PublicWebExternalMarketContextProvider:
    """Fetch public web context without project-specific API keys."""

    BTC_ACTIVE_ADDRESSES_URL = "https://api.blockchain.info/charts/n-unique-addresses"
    BTC_ETF_FLOW_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
    BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
    XRP_LEDGERS_URL = "https://api.xrpscan.com/api/v1/ledgers"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 3.0,
        cache_ttl_sec: float = 300.0,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)
        self._cache_ttl_sec = max(cache_ttl_sec, 0.0)
        self._monotonic_clock = monotonic_clock
        self._cache: dict[tuple[str, str], tuple[float, dict[str, object]]] = {}

    def fetch(self, *, market: str, trade_coin: str) -> dict[str, dict[str, object]]:
        coin = trade_coin.upper()
        payload: dict[str, dict[str, object]] = {}
        errors: dict[str, object] = {}
        onchain, onchain_error = self._fetch_optional(("onchain", coin), lambda: self._fetch_onchain(coin))
        if onchain_error:
            errors["onchain"] = onchain_error
        elif onchain:
            payload["onchain"] = onchain

        etf, etf_error = self._fetch_optional(("etf", coin), lambda: self._fetch_etf(coin))
        if etf_error:
            errors["etf"] = etf_error
        elif etf:
            payload["etf"] = etf

        market_data, market_error = self._fetch_optional(("market_data", coin), lambda: self._fetch_market_data(coin))
        if market_error:
            errors["market_data"] = market_error
        elif market_data:
            payload["market_data"] = market_data

        if errors:
            payload["_errors"] = errors
        return payload

    def close(self) -> None:
        self._client.close()

    def _fetch_optional(
        self,
        cache_key: tuple[str, str],
        fetcher: Callable[[], dict[str, object]],
    ) -> tuple[dict[str, object], str]:
        cached = self._cache.get(cache_key)
        now = self._monotonic_clock()
        if cached and cached[0] > now:
            return dict(cached[1]), ""
        try:
            payload = fetcher()
        except Exception as exc:
            return {}, str(exc)
        if self._cache_ttl_sec > 0:
            self._cache[cache_key] = (now + self._cache_ttl_sec, dict(payload))
        return payload, ""

    def _fetch_onchain(self, coin: str) -> dict[str, object]:
        if coin == "BTC":
            return self._fetch_btc_onchain()
        if coin == "XRP":
            return self._fetch_xrp_onchain()
        return {}

    def _fetch_btc_onchain(self) -> dict[str, object]:
        response = self._client.get(
            self.BTC_ACTIVE_ADDRESSES_URL,
            params={"timespan": "8days", "format": "json", "sampled": "false"},
        )
        response.raise_for_status()
        raw = response.json()
        values = raw.get("values", []) if isinstance(raw, dict) else []
        points = [item for item in values if isinstance(item, dict) and item.get("y") is not None]
        if len(points) < 2:
            return {}
        latest = float(points[-1]["y"])
        previous = float(points[-2]["y"])
        change_pct = 0.0 if previous == 0 else ((latest - previous) / previous) * 100
        return {
            "source": "web",
            "state": self._state_from_change(change_pct),
            "active_addresses_change_pct": round(change_pct, 3),
            "exchange_netflow_state": "neutral",
            "whale_activity_state": "unknown",
            "valuation_state": "unknown",
            "metric": "btc_unique_addresses",
        }

    def _fetch_xrp_onchain(self) -> dict[str, object]:
        response = self._client.get(self.XRP_LEDGERS_URL)
        response.raise_for_status()
        raw = response.json()
        ledgers = raw.get("ledgers", []) if isinstance(raw, dict) else []
        counts = [
            float(item.get("tx_count", 0))
            for item in ledgers
            if isinstance(item, dict) and item.get("tx_count") is not None
        ]
        if len(counts) < 2:
            return {}
        latest = counts[0]
        baseline_values = counts[1:]
        baseline = sum(baseline_values) / len(baseline_values)
        change_pct = 0.0 if baseline == 0 else ((latest - baseline) / baseline) * 100
        return {
            "source": "web",
            "state": self._state_from_change(change_pct),
            "active_addresses_change_pct": round(change_pct, 3),
            "exchange_netflow_state": "neutral",
            "whale_activity_state": "unknown",
            "valuation_state": "unknown",
            "metric": "xrp_recent_ledger_tx_count",
        }

    def _fetch_etf(self, coin: str) -> dict[str, object]:
        if coin != "BTC":
            return {}
        response = self._client.get(self.BTC_ETF_FLOW_URL)
        response.raise_for_status()
        flow_musd = self._parse_farside_total_flow_musd(response.text)
        if flow_musd is None:
            return {}
        return {
            "source": "web",
            "state": "inflow" if flow_musd > 0 else "outflow" if flow_musd < 0 else "neutral",
            "flow_usd": round(flow_musd * 1_000_000, 2),
            "inflow_usd": round(max(flow_musd, 0.0) * 1_000_000, 2),
            "outflow_usd": round(abs(min(flow_musd, 0.0)) * 1_000_000, 2),
            "metric": "farside_btc_etf_total_flow",
        }

    def _fetch_market_data(self, coin: str) -> dict[str, object]:
        response = self._client.get(self.BINANCE_TICKER_URL, params={"symbol": f"{coin}USDT"})
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict) or raw.get("lastPrice") is None:
            return {}
        return {
            "source": "web",
            "usd_price": float(raw["lastPrice"]),
            "usd_change_pct_24h": float(raw.get("priceChangePercent", 0.0)) / 100,
            "quote_volume_usd_24h": float(raw.get("quoteVolume", 0.0)),
        }

    @staticmethod
    def _state_from_change(change_pct: float) -> str:
        if change_pct >= 2.0:
            return "bullish"
        if change_pct <= -2.0:
            return "bearish"
        return "neutral"

    @staticmethod
    def _parse_farside_total_flow_musd(html: str) -> float | None:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
        for row in rows:
            cells = [
                PublicWebExternalMarketContextProvider._clean_cell(cell)
                for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
            ]
            if not cells or not re.match(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", cells[0]):
                continue
            for cell in reversed(cells[1:]):
                value = PublicWebExternalMarketContextProvider._parse_number_cell(cell)
                if value is not None:
                    return value
        return None

    @staticmethod
    def _clean_cell(value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value)
        return " ".join(without_tags.replace("\xa0", " ").split())

    @staticmethod
    def _parse_number_cell(value: str) -> float | None:
        stripped = value.strip()
        if not stripped or stripped == "-":
            return None
        negative = stripped.startswith("(") and stripped.endswith(")")
        normalized = stripped.strip("()").replace(",", "")
        try:
            parsed = float(normalized)
        except ValueError:
            return None
        return -parsed if negative else parsed


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
        market_payload = provider_payload.get("market_data", {})
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
        market_usd_price = self._float_value(market_payload.get("usd_price"), 0.0)
        etf_inflow_usd = self._float_value(etf_payload.get("inflow_usd"), max(etf_flow_usd, 0.0))
        etf_outflow_usd = self._float_value(etf_payload.get("outflow_usd"), abs(min(etf_flow_usd, 0.0)))
        etf_holding_change = self._float_value(
            etf_payload.get("holding_change_coin"),
            0.0 if market_usd_price <= 0 else etf_flow_usd / market_usd_price,
        )
        market_usd_change_pct = self._float_value(market_payload.get("usd_change_pct_24h"), 0.0)
        market_quote_volume_usd = self._float_value(market_payload.get("quote_volume_usd_24h"), 0.0)
        raw_whale_activity_state = onchain_payload.get("whale_activity_state")
        raw_valuation_state = onchain_payload.get("valuation_state")
        derived_whale_activity_state = self._derive_whale_activity_state(
            active_addresses_change_pct=onchain_active_addresses_change_pct,
            quote_volume_usd_24h=market_quote_volume_usd,
        )
        derived_valuation_state = self._derive_valuation_state(usd_change_pct_24h=market_usd_change_pct)
        whale_activity_state, whale_activity_derived = self._state_value(
            raw_whale_activity_state,
            fallback=derived_whale_activity_state,
        )
        valuation_state, valuation_derived = self._state_value(raw_valuation_state, fallback=derived_valuation_state)
        onchain_source = self._string_value(onchain_payload.get("source"), "http") if onchain_payload else self._config.onchain_source
        etf_source = self._string_value(etf_payload.get("source"), "http") if etf_payload else self._config.etf_source
        context = {
            "enabled": True,
            "market": market,
            "trade_coin": coin,
            "onchain": {
                "source": onchain_source,
                "state": onchain_state,
                "active_addresses_change_pct": onchain_active_addresses_change_pct,
                "exchange_netflow_state": onchain_exchange_netflow_state,
                "whale_activity_state": whale_activity_state,
                "whale_activity_basis": self._basis_value(
                    onchain_payload.get("whale_activity_basis"),
                    fallback="activity_volume_proxy",
                    derived=whale_activity_derived,
                ),
                "valuation_state": valuation_state,
                "valuation_basis": self._basis_value(
                    onchain_payload.get("valuation_basis"),
                    fallback="price_change_proxy",
                    derived=valuation_derived,
                ),
            },
            "etf": {
                "source": etf_source,
                "state": etf_state,
                "flow_usd": etf_flow_usd if coin in self.ETF_SUPPORTED_COINS else 0.0,
                "inflow_usd": etf_inflow_usd if coin in self.ETF_SUPPORTED_COINS else 0.0,
                "outflow_usd": etf_outflow_usd if coin in self.ETF_SUPPORTED_COINS else 0.0,
                "holding_change_coin": etf_holding_change if coin in self.ETF_SUPPORTED_COINS else 0.0,
            },
            "market_data": {
                "source": self._string_value(market_payload.get("source"), "web") if market_payload else "manual",
                "usd_price": market_usd_price,
                "usd_change_pct_24h": market_usd_change_pct,
                "quote_volume_usd_24h": market_quote_volume_usd,
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
                if key in {"onchain", "etf", "market_data"} and value
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
    def _derive_whale_activity_state(*, active_addresses_change_pct: float, quote_volume_usd_24h: float) -> str:
        if quote_volume_usd_24h >= 1_000_000_000 or abs(active_addresses_change_pct) >= 15:
            return "bullish" if active_addresses_change_pct >= 0 else "bearish"
        if quote_volume_usd_24h >= 100_000_000 or abs(active_addresses_change_pct) >= 5:
            return "neutral"
        return "neutral"

    @staticmethod
    def _derive_valuation_state(*, usd_change_pct_24h: float) -> str:
        if usd_change_pct_24h >= 0.08:
            return "bearish"
        if usd_change_pct_24h <= -0.08:
            return "bullish"
        return "neutral"

    @staticmethod
    def _string_value(value: Any, fallback: str) -> str:
        if value is None:
            return fallback
        return str(value).strip() or fallback

    @staticmethod
    def _state_value(value: Any, *, fallback: str) -> tuple[str, bool]:
        state = ExternalMarketContextService._string_value(value, fallback)
        if state == "unknown":
            return fallback, True
        return state, state == fallback and (value is None or str(value).strip() == "")

    @staticmethod
    def _basis_value(value: Any, *, fallback: str, derived: bool) -> str:
        if value is not None and str(value).strip():
            return str(value).strip()
        return fallback if derived else ""

    @staticmethod
    def _float_value(value: Any, fallback: float) -> float:
        if value is None or value == "":
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
