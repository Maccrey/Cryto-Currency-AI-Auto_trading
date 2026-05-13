from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier


def test_market_trend_classifier_marks_box_range_from_price_history() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=801.0)
    store.save(market="KRW-XRP", price=802.0)

    trend = MarketTrendClassifier().classify(
        current_price=802.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.0025
    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.box_range_low == 800.0
    assert trend.box_range_high == 802.0


def test_market_trend_classifier_marks_bull_and_bear() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=804.0)

    bull = MarketTrendClassifier().classify(
        current_price=804.0,
        history=store.list_history("KRW-XRP"),
    )

    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=804.0)
    store.save(market="KRW-XRP", price=800.0)

    bear = MarketTrendClassifier().classify(
        current_price=800.0,
        history=store.list_history("KRW-XRP"),
    )

    assert bull.market_state == "bull"
    assert bull.market_state_label == "상승장"
    assert bear.market_state == "bear"
    assert bear.market_state_label == "하락장"
