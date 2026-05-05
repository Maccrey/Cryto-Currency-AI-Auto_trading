from app.services.market.context import (
    ExternalMarketContextConfig,
    ExternalMarketContextService,
)


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
