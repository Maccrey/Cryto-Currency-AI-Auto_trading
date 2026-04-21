from app.services.dashboard.market import DashboardMarketService
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.market.store import MarketPriceStore


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
