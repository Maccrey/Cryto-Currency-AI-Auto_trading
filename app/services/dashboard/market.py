from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.market.store import MarketPriceSnapshot, MarketPriceStore
from app.services.market.trend import MarketTrendClassifier
from app.services.learning.service import LearningService


@dataclass(frozen=True)
class DashboardMarket:
    market: str
    state_label: str
    state_message: str
    severity: str
    current_price: float
    recorded_at: str
    recent_change_pct: float
    history: list[dict[str, object]]
    market_state: str = "box"
    market_state_label: str = "박스권"
    box_range_low: float | None = None
    box_range_high: float | None = None
    learning_sample_count: int = 0
    learning_confidence: float = 0.0
    market_state_source: str = "price_history"


class DashboardChartFeed:
    """Build chart-ready market history payloads."""

    def build(
        self,
        *,
        history: list[MarketPriceSnapshot],
        market_price_store: MarketPriceStore,
    ) -> list[dict[str, object]]:
        return [market_price_store.to_payload(item) for item in history]


class DashboardMarketSummaryFeed:
    """Build dashboard-friendly market summary payloads."""

    def __init__(
        self,
        *,
        chart_feed: DashboardChartFeed | None = None,
        trend_classifier: MarketTrendClassifier | None = None,
        learning_service: LearningService | None = None,
    ) -> None:
        self._chart_feed = chart_feed or DashboardChartFeed()
        self._trend_classifier = trend_classifier or MarketTrendClassifier()
        self._learning_service = learning_service

    def build(
        self,
        *,
        snapshot: MarketPriceSnapshot | None,
        history: list[MarketPriceSnapshot],
        market_price_store: MarketPriceStore,
        reference_change_pct: float | None = None,
    ) -> DashboardMarket | None:
        if snapshot is None:
            return None

        trend = self._trend_classifier.classify(
            current_price=snapshot.price,
            history=history,
            learning_events=[] if self._learning_service is None else self._learning_service.recent_events(limit=200),
            reference_change_pct=reference_change_pct,
        )
        recent_change_pct = trend.recent_change_pct
        state_label = self._derive_state_label(recent_change_pct)
        state_message = self._derive_state_message(recent_change_pct)
        severity = self._derive_severity(recent_change_pct)

        return DashboardMarket(
            market=snapshot.market,
            state_label=state_label,
            state_message=state_message,
            severity=severity,
            current_price=snapshot.price,
            recorded_at=snapshot.recorded_at,
            recent_change_pct=recent_change_pct,
            history=self._chart_feed.build(
                history=history,
                market_price_store=market_price_store,
            ),
            market_state=trend.market_state,
            market_state_label=trend.market_state_label,
            box_range_low=trend.box_range_low,
            box_range_high=trend.box_range_high,
            learning_sample_count=trend.learning_sample_count,
            learning_confidence=trend.learning_confidence,
            market_state_source=trend.source,
        )

    @staticmethod
    def to_payload(market: DashboardMarket) -> dict[str, object]:
        payload = asdict(market)
        if not payload.get("learning_sample_count"):
            payload.pop("learning_sample_count", None)
            payload.pop("learning_confidence", None)
        return payload

    @staticmethod
    def _derive_state_label(recent_change_pct: float) -> str:
        if recent_change_pct > 0:
            return "UP"
        if recent_change_pct < 0:
            return "DOWN"
        return "FLAT"

    @staticmethod
    def _derive_state_message(recent_change_pct: float) -> str:
        if recent_change_pct > 0:
            return "최근 구간 기준 상승 흐름입니다."
        if recent_change_pct < 0:
            return "최근 구간 기준 하락 흐름입니다."
        return "최근 구간 기준 보합 흐름입니다."

    @staticmethod
    def _derive_severity(recent_change_pct: float) -> str:
        if recent_change_pct < 0:
            return "warning"
        return "info"


class DashboardMarketService(DashboardMarketSummaryFeed):
    """Backward-compatible market summary service."""
