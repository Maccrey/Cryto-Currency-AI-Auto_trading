from app.services.market.store import MarketPriceStore


def test_market_price_store_saves_and_reads_latest_price() -> None:
    store = MarketPriceStore(
        timestamp_provider=lambda: "2026-04-19T20:00:00+09:00",
    )

    snapshot = store.save(market="KRW-XRP", price=845.5)

    assert snapshot.market == "KRW-XRP"
    assert snapshot.price == 845.5
    assert snapshot.recorded_at == "2026-04-19T20:00:00+09:00"
    assert store.get("KRW-XRP") == snapshot
    assert store.get_price("KRW-XRP") == 845.5
    assert store.get("KRW-BTC") is None


def test_market_price_store_keeps_recent_history_in_order() -> None:
    timestamps = iter(
        [
            "2026-04-19T20:00:00+09:00",
            "2026-04-19T20:00:01+09:00",
            "2026-04-19T20:00:02+09:00",
        ],
    )
    store = MarketPriceStore(
        history_limit=2,
        timestamp_provider=lambda: next(timestamps),
    )

    store.save(market="KRW-XRP", price=820.0)
    store.save(market="KRW-XRP", price=825.0)
    store.save(market="KRW-XRP", price=830.0)

    history = store.list_history("KRW-XRP")

    assert [snapshot.price for snapshot in history] == [825.0, 830.0]
    assert [snapshot.recorded_at for snapshot in history] == [
        "2026-04-19T20:00:01+09:00",
        "2026-04-19T20:00:02+09:00",
    ]
