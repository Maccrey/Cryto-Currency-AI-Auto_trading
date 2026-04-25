from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.market.store import MarketPriceSnapshot, MarketPriceStore


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

    def __init__(self, *, chart_feed: DashboardChartFeed | None = None) -> None:
        self._chart_feed = chart_feed or DashboardChartFeed()

    def build(
        self,
        *,
        snapshot: MarketPriceSnapshot | None,
        history: list[MarketPriceSnapshot],
        market_price_store: MarketPriceStore,
    ) -> DashboardMarket | None:
        if snapshot is None:
            return None

        recent_change_pct = 0.0
        if len(history) >= 2 and history[0].price > 0:
            recent_change_pct = round(
                (snapshot.price - history[0].price) / history[0].price,
                4,
            )
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
        )

    @staticmethod
    def to_payload(market: DashboardMarket) -> dict[str, object]:
        return asdict(market)

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
