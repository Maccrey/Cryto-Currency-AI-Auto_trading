from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeEvent:
    event_type: str
    market: str
    price: float
    quantity: float
    timestamp: str
    reason: str
    stop_loss_price: float | None


@dataclass(frozen=True)
class ChartMarker:
    event_type: str
    market: str
    color: str
    price: float
    timestamp: str
    tooltip: dict[str, object]


class MarkerTooltipSchema:
    """Build the stable tooltip payload for dashboard trade markers."""

    def build(self, event: TradeEvent) -> dict[str, object]:
        return {
            "market": event.market,
            "price": event.price,
            "quantity": event.quantity,
            "reason": event.reason,
            "stop_loss_price": event.stop_loss_price,
        }


class DashboardMarkerService:
    """Convert trading events into chart markers and tooltip payloads."""

    COLORS = {
        "buy": "blue",
        "sell": "red",
        "stop_loss": "yellow",
    }

    def __init__(self, *, tooltip_schema: MarkerTooltipSchema | None = None) -> None:
        self._tooltip_schema = tooltip_schema or MarkerTooltipSchema()

    def build_marker(self, event: TradeEvent) -> ChartMarker:
        return ChartMarker(
            event_type=event.event_type,
            market=event.market,
            color=self.COLORS[event.event_type],
            price=event.price,
            timestamp=event.timestamp,
            tooltip=self._tooltip_schema.build(event),
        )
