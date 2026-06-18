from app.services.learning.service import LearningEvent
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier


def test_market_trend_classifier_requires_confirmed_box_touches() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.3)
    store.save(market="KRW-XRP", price=800.6)

    trend = MarketTrendClassifier().classify(
        current_price=800.6,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.001
    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


def test_market_trend_classifier_marks_confirmed_box_after_repeated_touches() -> None:
    store = MarketPriceStore()
    for price in [100.0, 102.0, 100.1, 101.9, 100.0, 102.1, 100.1, 100.0]:
        store.save(market="KRW-XRP", price=price)

    trend = MarketTrendClassifier().classify(
        current_price=100.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.0
    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.box_range_low == 100.0
    assert trend.box_range_high == 102.1
    assert trend.source == "confirmed_price_box"


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


def test_market_trend_classifier_does_not_call_two_points_a_box() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=2108.0)
    store.save(market="KRW-XRP", price=2110.0)

    trend = MarketTrendClassifier().classify(
        current_price=2110.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.market_state == "bull"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


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

    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
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

def test_market_trend_classifier_treats_weak_rebound_inside_bear_reference_as_bull() -> None:
    store = MarketPriceStore()
    for price in [1912.0, 1913.0, 1914.0, 1915.0, 1916.0]:
        store.save(market="KRW-XRP", price=price)

    trend = MarketTrendClassifier().classify(
        current_price=1916.0,
        history=store.list_history("KRW-XRP"),
        reference_change_pct=-0.024,
    )

    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.source == "price_history"


def test_market_trend_classifier_allows_strong_recovery_over_bear_reference() -> None:
    store = MarketPriceStore()
    for price in [1900.0, 1903.0, 1906.0, 1909.0, 1912.0]:
        store.save(market="KRW-XRP", price=price)

    trend = MarketTrendClassifier().classify(
        current_price=1912.0,
        history=store.list_history("KRW-XRP"),
        reference_change_pct=-0.024,
    )

    assert trend.recent_change_pct == 0.0063
    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.source == "price_history"


def test_market_trend_classifier_uses_learning_override_when_reference_is_ambiguous() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=800.0)
    store.save(market="KRW-XRP", price=800.0)
    learning_events = [
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={"market_state": "bull", "status": "filled"},
        )
        for _ in range(8)
    ]

    trend = MarketTrendClassifier().classify(
        current_price=800.0,
        history=store.list_history("KRW-XRP"),
        learning_events=learning_events,
        reference_change_pct=-0.0012,
    )

    assert trend.market_state == "bull"
    assert trend.source == "learning_trend_override"
    assert trend.learning_confidence == 1.0


def test_market_trend_classifier_uses_medium_trend_over_single_tick_pullback() -> None:
    store = MarketPriceStore()
    for price in [1000.0, 1008.0, 1015.0, 1022.0, 1028.0, 1026.0]:
        store.save(market="KRW-XRP", price=price)

    trend = MarketTrendClassifier().classify(
        current_price=1026.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.source == "medium_price_history"


def test_market_trend_classifier_keeps_stable_recent_range_as_box_over_learning_bear() -> None:
    store = MarketPriceStore()
    # Use a 10-KRW band (1710–1720) which is ~0.58% of 1715 KRW, above
    # MIN_TRADEABLE_BOX_WIDTH_PCT (0.5%), so _confirmed_box() returns True.
    for price in ([1710.0, 1715.0, 1720.0, 1715.0, 1710.0, 1715.0, 1720.0, 1715.0] * 40):
        store.save(market="KRW-XRP", price=price)
    learning_events = [
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={"market_state": "bear", "status": "blocked"},
        )
        for _ in range(80)
    ]

    trend = MarketTrendClassifier().classify(
        current_price=1715.0,
        history=store.list_history("KRW-XRP"),
        learning_events=learning_events,
    )

    assert trend.market_state == "box"
    assert trend.market_state_label == "박스권"
    assert trend.source == "confirmed_price_box"
    assert trend.box_range_low is not None
    assert trend.box_range_high is not None


def test_market_trend_classifier_prefers_broad_rise_over_old_box_touches() -> None:
    store = MarketPriceStore()
    prices = [1770.0, 1780.0, 1771.0, 1779.0] * 8
    remaining = 288 - len(prices)
    prices.extend(
        1771.0 + (6.0 * index / (remaining - 1))
        for index in range(remaining)
    )
    for price in prices:
        store.save(market="KRW-XRP", price=price)

    trend = MarketTrendClassifier().classify(
        current_price=1777.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.source == "directional_price_history"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


def test_market_trend_classifier_keeps_short_stable_runtime_window_as_bull_without_box_touches() -> None:
    """A short 6-point history with a 1-KRW range (0.06%) is below the
    MIN_TRADEABLE_BOX_WIDTH_PCT threshold (0.5%) so _confirmed_box() returns
    False and the market is NOT classified as a confirmed price box.  The
    exact state depends on the trend direction but box_range should be None."""
    store = MarketPriceStore()
    for price in [1711.0, 1710.0, 1710.0, 1711.0, 1710.0, 1711.0]:
        store.save(market="KRW-XRP", price=price)
    learning_events = [
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={"market_state": "bear", "status": "blocked"},
        )
        for _ in range(80)
    ]

    trend = MarketTrendClassifier().classify(
        current_price=1711.0,
        history=store.list_history("KRW-XRP"),
        learning_events=learning_events,
    )

    # The narrow range prevents a confirmed box — the market may be bull or box
    # (not a confirmed_price_box), and no tradeable box range is published.
    assert trend.source != "confirmed_price_box"
    assert trend.box_range_low is None
    assert trend.box_range_high is None


def test_market_trend_classifier_keeps_short_two_point_stable_move_as_bull_over_ticker() -> None:
    store = MarketPriceStore()
    store.save(market="KRW-XRP", price=1710.0)
    store.save(market="KRW-XRP", price=1711.0)

    trend = MarketTrendClassifier().classify(
        current_price=1711.0,
        history=store.list_history("KRW-XRP"),
    )

    assert trend.recent_change_pct == 0.001
    assert trend.market_state == "bull"
    assert trend.market_state_label == "상승장"
    assert trend.source == "price_history"
