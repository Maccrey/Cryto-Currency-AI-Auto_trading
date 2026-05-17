from app.services.dashboard.market import (
    DashboardChartFeed,
    DashboardMarketService,
    DashboardMarketSummaryFeed,
)
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.market.store import MarketPriceStore
from app.services.market.upbit_ticker import UpbitTickerSnapshot


class CurrentPriceProviderStub:
    def __init__(self, price: float | None) -> None:
        self.price = price
        self.calls: list[str] = []

    def get_current_price(self, market: str) -> float | None:
        self.calls.append(market)
        return self.price


class CurrentTickerProviderStub:
    def __init__(self, snapshot: UpbitTickerSnapshot | None) -> None:
        self.snapshot = snapshot
        self.calls: list[str] = []

    def get_current_price(self, market: str) -> float | None:
        self.calls.append(market)
        return None if self.snapshot is None else self.snapshot.trade_price

    def get_current_snapshot(self, market: str) -> UpbitTickerSnapshot | None:
        self.calls.append(market)
        return self.snapshot


def test_dashboard_market_facade_returns_empty_without_snapshot() -> None:
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=MarketPriceStore(),
        dashboard_market_service=DashboardMarketService(),
    )

    payload = facade.build_current_response()

    assert payload == {
        "status": "empty",
        "market": "KRW-XRP",
        "summary": None,
    }


def test_dashboard_market_facade_fetches_current_price_when_store_is_empty() -> None:
    store = MarketPriceStore(
        timestamp_provider=lambda: "2026-04-19T20:35:00+09:00",
    )
    provider = CurrentPriceProviderStub(845.5)
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
        current_price_provider=provider,
    )

    payload = facade.build_current_response()

    assert provider.calls == ["KRW-XRP"]
    assert payload["status"] == "ok"
    assert payload["summary"]["current_price"] == 845.5
    assert payload["summary"]["recorded_at"] == "2026-04-19T20:35:00+09:00"
    assert store.get_price("KRW-XRP") == 845.5


def test_dashboard_market_facade_refreshes_current_price_when_provider_exists() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:35:00+09:00",
            "2026-04-19T20:35:01+09:00",
        ],
    )
    store = MarketPriceStore(
        timestamp_provider=lambda: next(timestamps),
    )
    store.save(market="KRW-XRP", price=845.5)
    provider = CurrentPriceProviderStub(846.0)
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
        current_price_provider=provider,
    )

    payload = facade.build_current_response()

    assert provider.calls == ["KRW-XRP"]
    assert payload["summary"]["current_price"] == 846.0
    assert payload["summary"]["recorded_at"] == "2026-04-19T20:35:01+09:00"
    assert [item["price"] for item in payload["summary"]["history"]] == [845.5, 846.0]


def test_dashboard_market_facade_includes_ticker_volume_when_provider_supports_snapshot() -> None:
    store = MarketPriceStore(
        timestamp_provider=lambda: "2026-04-19T20:35:00+09:00",
    )
    provider = CurrentTickerProviderStub(
        UpbitTickerSnapshot(
            trade_price=846.0,
            signed_change_rate=0.0123,
            acc_trade_volume_24h=123456.789,
            acc_trade_price_24h=255000000.0,
        ),
    )
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
        current_price_provider=provider,
    )

    payload = facade.build_current_response()

    assert provider.calls == ["KRW-XRP"]
    assert payload["summary"]["current_price"] == 846.0
    assert payload["summary"]["signed_change_rate"] == 0.0123
    assert payload["summary"]["acc_trade_volume_24h"] == 123456.789
    assert payload["summary"]["acc_trade_price_24h"] == 255000000.0
    assert payload["summary"]["market_state"] == "bull"
    assert payload["summary"]["market_state_label"] == "상승장"


def test_dashboard_market_facade_does_not_duplicate_unchanged_provider_price() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:35:00+09:00",
            "2026-04-19T20:35:01+09:00",
        ],
    )
    store = MarketPriceStore(
        timestamp_provider=lambda: next(timestamps),
    )
    store.save(market="KRW-XRP", price=846.0)
    provider = CurrentTickerProviderStub(
        UpbitTickerSnapshot(
            trade_price=846.0,
            signed_change_rate=-0.011,
        ),
    )
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
        current_price_provider=provider,
    )

    payload = facade.build_current_response()

    assert [item["price"] for item in payload["summary"]["history"]] == [846.0]
    assert payload["summary"]["recorded_at"] == "2026-04-19T20:35:00+09:00"
    assert payload["summary"]["market_state"] == "bear"
    assert payload["summary"]["market_state_label"] == "하락장"


def test_dashboard_market_facade_returns_current_price_change_and_history() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:30:00+09:00",
            "2026-04-19T20:30:01+09:00",
            "2026-04-19T20:30:02+09:00",
        ],
    )
    store = MarketPriceStore(
        timestamp_provider=lambda: next(timestamps),
    )
    store.save(market="KRW-XRP", price=820.0)
    store.save(market="KRW-XRP", price=825.0)
    store.save(market="KRW-XRP", price=830.0)
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
    )

    payload = facade.build_current_response(history_limit=2)

    assert payload == {
        "status": "ok",
        "market": "KRW-XRP",
        "summary": {
            "market": "KRW-XRP",
            "state_label": "UP",
            "state_message": "최근 구간 기준 상승 흐름입니다.",
            "severity": "info",
            "current_price": 830.0,
            "recorded_at": "2026-04-19T20:30:02+09:00",
            "recent_change_pct": 0.0061,
            "market_state": "bull",
            "market_state_label": "상승장",
            "box_range_low": None,
            "box_range_high": None,
            "history": [
                {
                    "market": "KRW-XRP",
                    "price": 825.0,
                    "recorded_at": "2026-04-19T20:30:01+09:00",
                },
                {
                    "market": "KRW-XRP",
                    "price": 830.0,
                    "recorded_at": "2026-04-19T20:30:02+09:00",
                },
            ],
        },
    }


def test_dashboard_market_service_splits_summary_and_chart_feeds() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:32:00+09:00",
            "2026-04-19T20:32:01+09:00",
        ],
    )
    store = MarketPriceStore(
        timestamp_provider=lambda: next(timestamps),
    )
    first = store.save(market="KRW-XRP", price=820.0)
    latest = store.save(market="KRW-XRP", price=830.0)
    chart_feed = DashboardChartFeed()
    summary_feed = DashboardMarketSummaryFeed(chart_feed=chart_feed)

    summary = summary_feed.build(
        snapshot=latest,
        history=[first, latest],
        market_price_store=store,
    )

    assert summary is not None
    assert summary.current_price == 830.0
    assert summary.recent_change_pct == 0.0122
    assert summary.history == [
        {
            "market": "KRW-XRP",
            "price": 820.0,
            "recorded_at": "2026-04-19T20:32:00+09:00",
        },
        {
            "market": "KRW-XRP",
            "price": 830.0,
            "recorded_at": "2026-04-19T20:32:01+09:00",
        },
    ]


def test_dashboard_market_facade_marks_downtrend_as_warning() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:31:00+09:00",
            "2026-04-19T20:31:01+09:00",
        ],
    )
    store = MarketPriceStore(
        timestamp_provider=lambda: next(timestamps),
    )
    store.save(market="KRW-XRP", price=830.0)
    store.save(market="KRW-XRP", price=820.0)
    facade = DashboardMarketFacade(
        market="KRW-XRP",
        market_price_store=store,
        dashboard_market_service=DashboardMarketService(),
    )

    payload = facade.build_current_response(history_limit=2)

    assert payload["summary"]["state_label"] == "DOWN"
    assert payload["summary"]["state_message"] == "최근 구간 기준 하락 흐름입니다."
    assert payload["summary"]["severity"] == "warning"
