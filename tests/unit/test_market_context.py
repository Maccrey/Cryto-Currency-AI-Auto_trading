from app.services.market.context import (
    ExternalMarketContextConfig,
    ExternalMarketContextService,
    HttpExternalMarketContextProvider,
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
