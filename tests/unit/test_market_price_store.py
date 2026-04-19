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
