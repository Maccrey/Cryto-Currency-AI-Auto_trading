from app.services.market.store import MarketPriceStore


def test_market_price_store_saves_and_reads_latest_price() -> None:
    store = MarketPriceStore()

    store.save(market="KRW-XRP", price=845.5)

    assert store.get("KRW-XRP") == 845.5
    assert store.get("KRW-BTC") is None
