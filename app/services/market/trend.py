from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.learning.service import LearningEvent
from app.services.market.store import MarketPriceSnapshot


@dataclass(frozen=True)
class MarketTrendSnapshot:
    recent_change_pct: float
    market_state: str
    market_state_label: str
    box_range_low: float | None = None
    box_range_high: float | None = None
    learning_sample_count: int = 0
    learning_confidence: float = 0.0
    source: str = "price_history"


class MarketTrendClassifier:
    """Classify the price-card trend state from recent market price history."""

    BOX_THRESHOLD_PCT = 0.001
    BEAR_REFERENCE_THRESHOLD_PCT = -0.01
    BEAR_MARKET_RECOVERY_THRESHOLD_PCT = 0.004
    MIN_BOX_WIDTH_PCT = 0.001
    RECENT_TREND_POINTS = 12
    STATE_LOOKBACK_POINTS = 288
    LEARNING_BOX_OVERRIDE_CONFIDENCE = 0.65
    LEARNING_TREND_OVERRIDE_CONFIDENCE = 0.82

    def classify(
        self,
        *,
        current_price: float,
        history: list[MarketPriceSnapshot],
        learning_events: list[LearningEvent] | None = None,
        reference_change_pct: float | None = None,
    ) -> MarketTrendSnapshot:
        state_history = self._state_history(history)
        recent_change_pct = 0.0
        if len(state_history) >= 2 and state_history[0].price > 0:
            recent_change_pct = round(
                (current_price - state_history[0].price) / state_history[0].price,
                4,
            )
        recent_window_change_pct = self._recent_window_change_pct(
            current_price=current_price,
            history=state_history,
        )
        state_change_pct, state_source = self._state_change_pct(
            recent_change_pct=recent_change_pct,
            recent_window_change_pct=recent_window_change_pct,
            reference_change_pct=reference_change_pct,
        )
        price_market_state = self._market_state(recent_change_pct=state_change_pct)
        learned_state, learned_confidence, sample_count = self._learned_market_state(
            learning_events or [],
        )
        market_state = price_market_state
        box_range_low, box_range_high = self._box_range(
            market_state=market_state,
            current_price=current_price,
            history=state_history,
        )
        return MarketTrendSnapshot(
            recent_change_pct=state_change_pct,
            market_state=market_state,
            market_state_label=self._market_state_label(market_state),
            box_range_low=box_range_low,
            box_range_high=box_range_high,
            learning_sample_count=sample_count,
            learning_confidence=learned_confidence,
            source=state_source,
        )

    @staticmethod
    def _state_history(history: list[MarketPriceSnapshot]) -> list[MarketPriceSnapshot]:
        if len(history) <= MarketTrendClassifier.STATE_LOOKBACK_POINTS:
            return history
        return history[-MarketTrendClassifier.STATE_LOOKBACK_POINTS :]

    @staticmethod
    def _state_change_pct(
        *,
        recent_change_pct: float,
        recent_window_change_pct: float,
        reference_change_pct: float | None,
    ) -> tuple[float, str]:
        reference = None if reference_change_pct is None else round(reference_change_pct, 4)
        if (
            reference is not None
            and reference <= MarketTrendClassifier.BEAR_REFERENCE_THRESHOLD_PCT
            and recent_window_change_pct > MarketTrendClassifier.BOX_THRESHOLD_PCT
            and recent_window_change_pct < MarketTrendClassifier.BEAR_MARKET_RECOVERY_THRESHOLD_PCT
        ):
            return 0.0, "bear_reference_box"
        if abs(recent_window_change_pct) > MarketTrendClassifier.BOX_THRESHOLD_PCT:
            return recent_window_change_pct, "price_history"
        if reference is None:
            return recent_change_pct, "price_history"
        if abs(reference) <= MarketTrendClassifier.BOX_THRESHOLD_PCT and abs(recent_change_pct) > MarketTrendClassifier.BOX_THRESHOLD_PCT:
            return recent_change_pct, "price_history"
        return reference, "ticker_reference"

    @staticmethod
    def _recent_window_change_pct(
        *,
        current_price: float,
        history: list[MarketPriceSnapshot],
    ) -> float:
        if len(history) < 2:
            return 0.0
        prices = [item.price for item in history if item.price > 0]
        if not prices:
            return 0.0
        if prices[-1] != current_price and current_price > 0:
            prices.append(current_price)
        if len(prices) < 2:
            return 0.0

        last_index = len(prices) - 1
        previous_index = last_index - 1
        while previous_index >= 0 and prices[last_index] == prices[previous_index]:
            previous_index -= 1
        if previous_index < 0:
            return 0.0

        direction = 1 if prices[last_index] > prices[previous_index] else -1
        start_index = previous_index
        same_direction_moves = 1
        min_index = max(0, last_index - MarketTrendClassifier.RECENT_TREND_POINTS + 1)
        while start_index > min_index:
            previous_price = prices[start_index - 1]
            current_window_price = prices[start_index]
            if previous_price == current_window_price:
                start_index -= 1
                continue
            current_direction = 1 if current_window_price > previous_price else -1
            if current_direction != direction:
                break
            start_index -= 1
            same_direction_moves += 1

        if len(prices) > 2 and same_direction_moves < 2:
            return 0.0

        start_price = prices[start_index]
        if start_price <= 0:
            return 0.0
        return round((current_price - start_price) / start_price, 4)

    @staticmethod
    def _market_state(*, recent_change_pct: float) -> str:
        if abs(recent_change_pct) <= MarketTrendClassifier.BOX_THRESHOLD_PCT:
            return "box"
        return "bull" if recent_change_pct > 0 else "bear"

    @staticmethod
    def _market_state_label(market_state: str) -> str:
        return {
            "bull": "상승장",
            "bear": "하락장",
            "box": "박스권",
        }.get(market_state, "박스권")

    @staticmethod
    def _box_range(
        *,
        market_state: str,
        current_price: float,
        history: list[MarketPriceSnapshot],
    ) -> tuple[float | None, float | None]:
        if market_state != "box":
            return None, None
        prices = [item.price for item in history if item.price > 0]
        if not prices:
            prices = [current_price]
        low = min(prices)
        high = max(prices)
        if current_price > 0:
            min_width = current_price * MarketTrendClassifier.MIN_BOX_WIDTH_PCT
            actual_width = high - low
            if actual_width < min_width:
                midpoint = (low + high) / 2
                half_width = min_width / 2
                low = midpoint - half_width
                high = midpoint + half_width
        return round(low, 4), round(high, 4)

    @staticmethod
    def _learned_market_state(events: list[LearningEvent]) -> tuple[str | None, float, int]:
        weighted_counts = {"bull": 0.0, "bear": 0.0, "box": 0.0}
        sample_count = 0
        for event in events[-200:]:
            payload: dict[str, Any] = event.payload if isinstance(event.payload, dict) else {}
            state = payload.get("market_state")
            if state not in weighted_counts:
                continue
            weight = 1.0
            status = str(payload.get("status") or "")
            reason = str(payload.get("reason") or "")
            if status == "filled":
                weight += 0.35
            if reason in {"POSITION_EXIT_TRIGGERED", "DEMO_CASH_LIMIT", "REENTRY_BLOCK_ACTIVE"}:
                weight += 0.15
            weighted_counts[str(state)] += weight
            sample_count += 1
        if sample_count <= 0:
            return None, 0.0, 0
        learned_state, weight = max(weighted_counts.items(), key=lambda item: item[1])
        total_weight = sum(weighted_counts.values())
        confidence = 0.0 if total_weight <= 0 else round(weight / total_weight, 3)
        return learned_state, confidence, sample_count
