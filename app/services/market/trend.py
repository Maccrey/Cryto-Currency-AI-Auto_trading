from __future__ import annotations

from dataclasses import dataclass

from app.services.market.store import MarketPriceSnapshot


@dataclass(frozen=True)
class MarketTrendSnapshot:
    recent_change_pct: float
    market_state: str
    market_state_label: str
    box_range_low: float | None = None
    box_range_high: float | None = None


class MarketTrendClassifier:
    """Classify the price-card trend state from recent market price history."""

    def classify(
        self,
        *,
        current_price: float,
        history: list[MarketPriceSnapshot],
    ) -> MarketTrendSnapshot:
        recent_change_pct = 0.0
        if len(history) >= 2 and history[0].price > 0:
            recent_change_pct = round(
                (current_price - history[0].price) / history[0].price,
                4,
            )
        market_state = self._market_state(recent_change_pct=recent_change_pct)
        box_range_low, box_range_high = self._box_range(
            market_state=market_state,
            current_price=current_price,
            history=history,
        )
        return MarketTrendSnapshot(
            recent_change_pct=recent_change_pct,
            market_state=market_state,
            market_state_label=self._market_state_label(market_state),
            box_range_low=box_range_low,
            box_range_high=box_range_high,
        )

    @staticmethod
    def _market_state(*, recent_change_pct: float) -> str:
        if abs(recent_change_pct) <= 0.003:
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
        return round(min(prices), 4), round(max(prices), 4)
