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
    ).snapshot(market="KRW-DOGE", trade_coin="DOGE")

    assert context["market"] == "KRW-DOGE"
    assert context["trade_coin"] == "DOGE"
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
                    "whale_activity_state": "bullish",
                    "valuation_state": "neutral",
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
    assert context["onchain"]["whale_activity_state"] == "bullish"
    assert context["onchain"]["whale_activity_basis"] == ""
    assert context["onchain"]["valuation_state"] == "neutral"
    assert context["onchain"]["valuation_basis"] == ""
    assert context["etf"]["source"] == "http"
    assert context["etf"]["state"] == "inflow"
    assert context["etf"]["flow_usd"] == 12_500_000.0
    assert context["learning_weight"] == 1.2


def test_external_market_context_derives_missing_onchain_detail_states() -> None:
    class Provider:
        def fetch(self, *, market: str, trade_coin: str) -> dict[str, dict[str, object]]:
            return {
                "onchain": {
                    "source": "web",
                    "state": "bearish",
                    "active_addresses_change_pct": -18.0,
                    "exchange_netflow_state": "neutral",
                    "whale_activity_state": "unknown",
                    "valuation_state": "unknown",
                },
                "market_data": {
                    "source": "web",
                    "usd_price": 1.4,
                    "usd_change_pct_24h": 0.12,
                    "quote_volume_usd_24h": 1_500_000_000,
                },
            }

    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(enabled=True),
        provider=Provider(),
    ).snapshot(market="KRW-XRP", trade_coin="XRP")

    assert context["onchain"]["whale_activity_state"] == "bearish"
    assert context["onchain"]["whale_activity_basis"] == "activity_volume_proxy"
    assert context["onchain"]["valuation_state"] == "bearish"
    assert context["onchain"]["valuation_basis"] == "price_change_proxy"


def test_external_market_context_includes_etf_aum_and_holdings() -> None:
    class Provider:
        def fetch(self, *, market: str, trade_coin: str) -> dict[str, dict[str, object]]:
            return {
                "etf": {
                    "source": "web",
                    "state": "inflow",
                    "flow_usd": 8_940_533.82,
                    "inflow_usd": 8_940_533.82,
                    "outflow_usd": 0,
                    "holding_change_coin": 6_340_804.12766,
                    "total_aum_usd": 1_119_769_130,
                    "total_holding_coin": 828_326_979,
                }
            }

    context = ExternalMarketContextService(
        config=ExternalMarketContextConfig(enabled=True),
        provider=Provider(),
    ).snapshot(market="KRW-XRP", trade_coin="XRP")

    assert context["etf"]["source"] == "web"
    assert context["etf"]["state"] == "inflow"
    assert context["etf"]["flow_usd"] == 8_940_533.82
    assert context["etf"]["holding_change_coin"] == 6_340_804.12766
    assert context["etf"]["total_aum_usd"] == 1_119_769_130
    assert context["etf"]["total_holding_coin"] == 828_326_979


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
    assert context["etf"]["state"] == "neutral"


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
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/spot/inFlow"):
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {"date": "2026-05-01", "change": -1_000_000, "price": 0.48},
                        {"date": "2026-05-02", "change": 2_500_000, "price": 0.5},
                    ],
                },
            )
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/list"):
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {
                            "ticker": "XRPC",
                            "etfAssetHistoryVo": {
                                "netAssets": 100_000_000,
                                "btcAmount": 200_000_000,
                                "btcAmount24hChange": 5_000_000,
                            },
                        }
                    ],
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
    assert payload["etf"]["source"] == "web"
    assert payload["etf"]["state"] == "inflow"
    assert payload["etf"]["flow_usd"] == 2_500_000
    assert payload["etf"]["holding_change_coin"] == 5_000_000
    assert payload["etf"]["total_aum_usd"] == 100_000_000
    assert payload["etf"]["total_holding_coin"] == 200_000_000
    assert payload["market_data"]["usd_price"] == 0.5
    assert payload["market_data"]["usd_change_pct_24h"] == -0.012


def test_public_web_context_provider_parses_coinglass_inflow_outflow_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.binance.com":
            return httpx.Response(200, json={"lastPrice": "200.0", "priceChangePercent": "0", "quoteVolume": "1"})
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/spot/inFlow"):
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {"date": "2026-05-01", "inflow": 1_000_000, "outflow": 3_500_000},
                    ],
                },
            )
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/list"):
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {
                            "etfAssetHistoryVo": {
                                "netAssets": 50_000_000,
                                "btcAmount": 250_000,
                                "btcAmount24hChange": -12_500,
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"ledgers": [{"tx_count": 1}, {"tx_count": 1}]})

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-SOL", trade_coin="SOL")

    assert payload["etf"]["state"] == "outflow"
    assert payload["etf"]["flow_usd"] == -2_500_000
    assert payload["etf"]["inflow_usd"] == 1_000_000
    assert payload["etf"]["outflow_usd"] == 3_500_000
    assert payload["etf"]["total_aum_usd"] == 50_000_000
    assert payload["etf"]["total_holding_coin_change"] == -12_500


def test_public_web_context_provider_parses_coinglass_camel_flow_keys() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.binance.com":
            return httpx.Response(200, json={"lastPrice": "200.0", "priceChangePercent": "0", "quoteVolume": "1"})
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/spot/inFlow"):
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {"date": "2026-05-01", "inFlowUsd": 0, "outFlowUsd": 4_200_000},
                    ],
                },
            )
        if request.url.host == "capi.coinglass.com" and str(request.url.path).endswith("/list"):
            return httpx.Response(200, json={"code": "0", "data": []})
        return httpx.Response(200, json={"ledgers": [{"tx_count": 1}, {"tx_count": 1}]})

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-SOL", trade_coin="SOL")

    assert payload["etf"]["state"] == "outflow"
    assert payload["etf"]["flow_usd"] == -4_200_000
    assert payload["etf"]["inflow_usd"] == 0
    assert payload["etf"]["outflow_usd"] == 4_200_000


def test_public_web_context_provider_falls_back_to_xrp_insights_etf_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "capi.coinglass.com":
            return httpx.Response(200, json={"code": "0", "msg": "success", "success": True})
        return httpx.Response(
            200,
            text=(
                r'\"agentData\":{\"totalNetAssets\":1119769130,\"totalTokenHoldings\":828326979,'
                r'\"dailyNetInflow\":0,\"lastUpdated\":\"2025-12-01T17:00:00.000Z\",'
                r'\"etfs\":[{\"dailyNetInflow\":5786640},{\"dailyNetInflow\":3153893.82}]},'
                r'\"xrpData\":{\"price\":1.41}'
            ),
        )

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-XRP", trade_coin="XRP")

    assert payload["etf"]["source"] == "web"
    assert payload["etf"]["state"] == "inflow"
    assert payload["etf"]["flow_usd"] == 8_940_533.82
    assert payload["etf"]["inflow_usd"] == 8_940_533.82
    assert payload["etf"]["outflow_usd"] == 0
    assert payload["etf"]["holding_change_coin"] == 6_340_804.12766
    assert payload["etf"]["total_aum_usd"] == 1_119_769_130
    assert payload["etf"]["total_holding_coin"] == 828_326_979
    assert payload["etf"]["metric"] == "xrp_insights_etf_tracker"


def test_public_web_context_provider_does_not_treat_missing_coinglass_flow_as_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "capi.coinglass.com":
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {
                            "etfAssetHistoryVo": {
                                "netAssets": 50_000_000,
                                "btcAmount": 250_000,
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"lastPrice": "200.0", "priceChangePercent": "0", "quoteVolume": "1"})

    provider = PublicWebExternalMarketContextProvider(
        transport=httpx.MockTransport(handler),
    )

    payload = provider.fetch(market="KRW-SOL", trade_coin="SOL")

    assert payload["etf"]["state"] == "unknown"
    assert payload["etf"]["flow_usd"] == 0.0
    assert payload["etf"]["total_aum_usd"] == 50_000_000
