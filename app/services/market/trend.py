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
    MIN_BOX_WIDTH_PCT = 0.001
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
        recent_change_pct = 0.0
        if len(history) >= 2 and history[0].price > 0:
            recent_change_pct = round(
                (current_price - history[0].price) / history[0].price,
                4,
            )
        state_change_pct, state_source = self._state_change_pct(
            recent_change_pct=recent_change_pct,
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
            history=history,
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
    def _state_change_pct(
        *,
        recent_change_pct: float,
        reference_change_pct: float | None,
    ) -> tuple[float, str]:
        if reference_change_pct is None:
            return recent_change_pct, "price_history"
        reference = round(reference_change_pct, 4)
        if abs(reference) <= MarketTrendClassifier.BOX_THRESHOLD_PCT and abs(recent_change_pct) > MarketTrendClassifier.BOX_THRESHOLD_PCT:
            return recent_change_pct, "price_history"
        return reference, "ticker_reference"

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
