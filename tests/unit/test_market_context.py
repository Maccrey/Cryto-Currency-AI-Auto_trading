from app.services.market.context import (
    ExternalMarketContextConfig,
    ExternalMarketContextService,
    HttpExternalMarketContextProvider,
    PublicWebExternalMarketContextProvider,
)
import httpx


def test_external_market_context_defaults_to_neutral_for_any_coin() -> None:
    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(enabled=True),
    ).snapshot(market="KRW-SOL", trade_coin="SOL")

    assert context["market"] == "KRW-SOL"
    assert context["trade_coin"] == "SOL"
    assert context["onchain"]["state"] == "neutral"
    assert context["etf"]["state"] == "not_applicable"
    assert context["learning_weight"] == 1.0


def test_external_market_context_includes_btc_etf_and_onchain_bias() -> None:
    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(
            enabled=True,
            onchain_state="bullish",
            onchain_active_addresses_change_pct=0.12,
            onchain_exchange_netflow_state="outflow",
            etf_state="inflow",
            etf_flow_usd=125_000_000.0,
        ),
    ).snapshot(market="KRW-BTC", trade_coin="BTC")

    assert context["onchain"]["state"] == "bullish"
    assert context["onchain"]["active_addresses_change_pct"] == 0.12
    assert context["onchain"]["exchange_netflow_state"] == "outflow"
    assert context["etf"]["state"] == "inflow"
    assert context["etf"]["flow_usd"] == 125_000_000.0
    assert context["learning_weight"] > 1.0


def test_external_market_context_merges_http_provider_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["coin"] == "BTC"
        if str(request.url.path).endswith("/onchain"):
            return httpx.Response(
                200,
                json={
                    "state": "bullish",
                    "active_addresses_change_pct": 3.5,
                    "exchange_netflow_state": "outflow",
                },
            )
        return httpx.Response(200, json={"state": "inflow", "flow_usd": 12_500_000})

    provider = HttpExternalMarketContextProvider(
        onchain_url="https://context.example/onchain",
        etf_url="https://context.example/etf",
        transport=httpx.MockTransport(handler),
    )
    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(enabled=True),
        provider=provider,
    ).snapshot(market="KRW-BTC", trade_coin="BTC")

    assert context["onchain"]["source"] == "http"
    assert context["onchain"]["state"] == "bullish"
    assert context["onchain"]["active_addresses_change_pct"] == 3.5
    assert context["onchain"]["exchange_netflow_state"] == "outflow"
    assert context["etf"]["source"] == "http"
    assert context["etf"]["state"] == "inflow"
    assert context["etf"]["flow_usd"] == 12_500_000.0
    assert context["learning_weight"] == 1.2


def test_external_market_context_falls_back_to_manual_when_http_provider_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    provider = HttpExternalMarketContextProvider(
        onchain_url="https://context.example/onchain",
        transport=httpx.MockTransport(handler),
    )
    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(
            enabled=True,
            onchain_state="bearish",
        ),
        provider=provider,
    ).snapshot(market="KRW-XRP", trade_coin="XRP")

    assert context["onchain"]["source"] == "manual"
    assert context["onchain"]["state"] == "bearish"
    assert context["onchain"]["fetch_error"]
    assert context["etf"]["state"] == "not_applicable"


def test_http_external_market_context_provider_caches_successful_sections() -> None:
    calls = {"count": 0}
    now = {"value": 1000.0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(
            200,
            json={
                "state": "bullish",
                "active_addresses_change_pct": calls["count"],
                "exchange_netflow_state": "outflow",
            },
        )

    provider = HttpExternalMarketContextProvider(
        onchain_url="https://context.example/onchain",
        transport=httpx.MockTransport(handler),
        cache_ttl_sec=60,
        monotonic_clock=lambda: now["value"],
    )

    first = provider.fetch(market="KRW-BTC", trade_coin="BTC")
    second = provider.fetch(market="KRW-BTC", trade_coin="BTC")
    now["value"] += 61
    third = provider.fetch(market="KRW-BTC", trade_coin="BTC")

    assert calls["count"] == 2
    assert first["onchain"]["active_addresses_change_pct"] == 1.0
    assert second["onchain"]["active_addresses_change_pct"] == 1.0
    assert third["onchain"]["active_addresses_change_pct"] == 2.0


def test_public_web_context_provider_fetches_btc_onchain_and_etf_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.blockchain.info":
            return httpx.Response(
                200,
                json={
                    "values": [
                        {"x": 1, "y": 100_000},
                        {"x": 2, "y": 110_000},
                    ],
                },
            )
        if request.url.host == "api.binance.com":
            return httpx.Response(
                200,
                json={
                    "lastPrice": "100000.00",
                    "priceChangePercent": "2.50",
                    "quoteVolume": "123456789.0",
                },
            )
        return httpx.Response(
            200,
            text="""
            <table>
              <tr><th>Date</th><th>IBIT</th><th>Total</th></tr>
              <tr><td>02 Jan 2026</td><td>287.4</td><td>471.3</td></tr>
            </table>
            """,
        )

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-BTC", trade_coin="BTC")

    assert payload["onchain"]["source"] == "web"
    assert payload["onchain"]["state"] == "bullish"
    assert payload["onchain"]["active_addresses_change_pct"] == 10.0
    assert payload["etf"]["source"] == "web"
    assert payload["etf"]["state"] == "inflow"
    assert payload["etf"]["flow_usd"] == 471_300_000
    assert payload["market_data"]["usd_price"] == 100000.0
    assert payload["market_data"]["usd_change_pct_24h"] == 0.025


def test_public_web_context_provider_fetches_xrp_ledger_activity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.binance.com":
            return httpx.Response(
                200,
                json={
                    "lastPrice": "0.5000",
                    "priceChangePercent": "-1.20",
                    "quoteVolume": "123456.0",
                },
            )
        return httpx.Response(
            200,
            json={
                "ledgers": [
                    {"ledger_index": 3, "tx_count": 120},
                    {"ledger_index": 2, "tx_count": 90},
                    {"ledger_index": 1, "tx_count": 100},
                ],
            },
        )

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-XRP", trade_coin="XRP")

    assert payload["onchain"]["source"] == "web"
    assert payload["onchain"]["state"] == "bullish"
    assert payload["onchain"]["active_addresses_change_pct"] == 26.316
    assert "etf" not in payload
    assert payload["market_data"]["usd_price"] == 0.5
    assert payload["market_data"]["usd_change_pct_24h"] == -0.012
