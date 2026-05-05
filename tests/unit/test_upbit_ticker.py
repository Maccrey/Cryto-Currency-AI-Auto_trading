import httpx

from app.services.market.upbit_ticker import UpbitTickerPriceProvider


def test_upbit_ticker_provider_reads_signed_change_rate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/ticker"
        assert request.url.params["markets"] == "KRW-XRP"
        return httpx.Response(
            200,
            json=[
                {
                    "trade_price": 820.5,
                    "signed_change_rate": -0.0123,
                    "acc_trade_volume_24h": 1234.5,
                    "acc_trade_price_24h": 987654321.0,
                },
            ],
        )

    provider = UpbitTickerPriceProvider(
        base_url="https://api.upbit.com",
        transport=httpx.MockTransport(handler),
    )

    snapshot = provider.get_current_snapshot("KRW-XRP")

    assert snapshot is not None
    assert snapshot.trade_price == 820.5
    assert snapshot.signed_change_rate == -0.0123
    assert snapshot.acc_trade_volume_24h == 1234.5
    assert snapshot.acc_trade_price_24h == 987654321.0
