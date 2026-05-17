from app.services.learning.service import LearningEvent
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier


def test_market_trend_classifier_marks_box_range_from_price_history() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.5)
    store.save(market="KRW-XRP", price=801.0)

    trend = MarketTrendClassifier().classify(
        current_price=801.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.0013
    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.box_range_low == 799.699
    assert trend.box_range_high == 801.301


def test_market_trend_classifier_expands_too_narrow_box_range() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2108.0)
    store.save(market="KRW-XRP", price=2110.0)

    trend = MarketTrendClassifier().classify(
        current_price=2110.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.market_state == "box"
    assert trend.box_range_low == 2106.89
    assert trend.box_range_high == 2111.11


def test_market_trend_classifier_uses_reference_change_for_state() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2108.0)
    store.save(market="KRW-XRP", price=2110.0)

    trend = MarketTrendClassifier().classify(
        current_price=2110.0,
        history=store.list_history("KRW-XRP"),
        reference_change_pct=0.012,
    )

    assert trend.recent_change_pct == 0.012
    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


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


def test_market_trend_classifier_uses_learning_data_when_price_is_box() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=801.0)
    learning_events = [
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={"market_state": "bull", "status": "filled"},
        )
        for _ in range(6)
    ]

    trend = MarketTrendClassifier().classify(
        current_price=801.0,
        history=store.list_history("KRW-XRP"),
        learning_events=learning_events,
    )

    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.learning_sample_count == 6
    assert trend.source == "learning_data"
