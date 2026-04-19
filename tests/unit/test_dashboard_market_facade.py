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
