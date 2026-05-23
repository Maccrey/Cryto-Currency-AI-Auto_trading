from app.services.learning.service import LearningEvent
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier


def test_market_trend_classifier_marks_small_moves_as_box_range() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.3)
    store.save(market="KRW-XRP", price=800.6)

    trend = MarketTrendClassifier().classify(
        current_price=800.6,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.0008
    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.box_range_low == 799.8997
    assert trend.box_range_high == 800.7003


def test_market_trend_classifier_reacts_to_modest_price_move() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.5)
    store.save(market="KRW-XRP", price=801.0)

    trend = MarketTrendClassifier().classify(
        current_price=801.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.0013
    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


def test_market_trend_classifier_expands_too_narrow_box_range() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2108.0)
    store.save(market="KRW-XRP", price=2110.0)

    trend = MarketTrendClassifier().classify(
        current_price=2110.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.market_state == "box"
    assert trend.box_range_low == 2107.945
    assert trend.box_range_high == 2110.055


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


def test_market_trend_classifier_does_not_let_learning_data_override_current_price_state() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.6)
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
        current_price=800.6,
        history=store.list_history("KRW-XRP"),
        learning_events=learning_events,
    )

    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.learning_sample_count == 6
    assert trend.source == "price_history"


def test_market_trend_classifier_uses_price_history_when_reference_is_flat() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2033.0)
    store.save(market="KRW-XRP", price=2030.0)

    trend = MarketTrendClassifier().classify(
        current_price=2030.0,
        history=store.list_history("KRW-XRP"),
        reference_change_pct=0.0,
    )

    assert trend.recent_change_pct == -0.0015
    assert trend.market_state == "bear"
    assert trend.market_state_label == "하락장"
    assert trend.source == "price_history"


def test_market_trend_classifier_uses_recent_drop_over_positive_reference() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2040.0)
    store.save(market="KRW-XRP", price=2037.0)
    store.save(market="KRW-XRP", price=2034.0)
    store.save(market="KRW-XRP", price=2031.0)

    trend = MarketTrendClassifier().classify(
        current_price=2031.0,
        history=store.list_history("KRW-XRP"),
        reference_change_pct=0.018,
    )

    assert trend.recent_change_pct == -0.0044
    assert trend.market_state == "bear"
    assert trend.market_state_label == "하락장"
    assert trend.source == "price_history"
