import json
from pathlib import Path

import httpx

from app.services.learning.service import LearningService
from app.services.market.bootstrap import HistoricalMarketBootstrapService, UpbitHistoricalCandleProvider
from app.services.market.store import MarketPriceStore


def test_upbit_historical_candle_provider_fetches_recent_hourly_candles_oldest_first() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/candles/minutes/60"
        assert request.url.params["market"] == "KRW-XRP"
        assert request.url.params["count"] == "72"
        return httpx.Response(
            200,
            json=[
                {
                    "market": "KRW-XRP",
                    "candle_date_time_kst": "2026-06-13T09:00:00",
                    "opening_price": 100.0,
                    "high_price": 102.0,
                    "low_price": 99.0,
                    "trade_price": 101.0,
                    "candle_acc_trade_volume": 10.0,
                    "candle_acc_trade_price": 1010.0,
                },
                {
                    "market": "KRW-XRP",
                    "candle_date_time_kst": "2026-06-13T08:00:00",
                    "trade_price": 100.0,
                },
            ],
        )

    provider = UpbitHistoricalCandleProvider(
        base_url="https://api.upbit.com",
        transport=httpx.MockTransport(handler),
    )

    candles = provider.fetch_recent(market="KRW-XRP", count=72)

    assert [candle.trade_price for candle in candles] == [100.0, 101.0]
    assert candles[0].recorded_at == "2026-06-13T08:00:00+09:00"
    assert candles[1].candle_acc_trade_price == 1010.0


class StubCandleProvider:
    def __init__(self) -> None:
        self.calls = []

    def fetch_recent(self, *, market: str, count: int):
        from app.services.market.bootstrap import UpbitCandleSnapshot

        self.calls.append({"market": market, "count": count})
        return [
            UpbitCandleSnapshot(market=market, trade_price=100.0, recorded_at="2026-06-13T06:00:00+09:00"),
            UpbitCandleSnapshot(market=market, trade_price=101.0, recorded_at="2026-06-13T07:00:00+09:00"),
            UpbitCandleSnapshot(market=market, trade_price=102.0, recorded_at="2026-06-13T08:00:00+09:00"),
        ]


def test_historical_market_bootstrap_records_observations_and_seeds_price_history(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    price_store = MarketPriceStore()
    provider = StubCandleProvider()
    service = HistoricalMarketBootstrapService(
        market="KRW-XRP",
        trading_mode="demo",
        candle_provider=provider,
        market_price_store=price_store,
        learning_service=learning_service,
        observation_path=tmp_path / "market-observations.jsonl",
        candle_count=72,
    )

    result = service.bootstrap()

    assert result["candle_count"] == 3
    assert result["written_observation_count"] == 3
    assert result["latest_market_state"] == "bull"
    assert provider.calls == [{"market": "KRW-XRP", "count": 72}]
    assert [item.price for item in price_store.list_history("KRW-XRP")] == [100.0, 101.0, 102.0]
    rows = [
        json.loads(line)
        for line in (tmp_path / "market-observations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["source"] == "upbit_3d_bootstrap"
    assert rows[-1]["market_state"] == "bull"
    assert learning_service.recent_events(limit=1)[0].event_name == "market_history_bootstrapped"

    second_result = service.bootstrap()

    assert second_result["written_observation_count"] == 0
    assert len((tmp_path / "market-observations.jsonl").read_text(encoding="utf-8").splitlines()) == 3
