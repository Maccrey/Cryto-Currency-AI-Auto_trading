from __future__ import annotations

from dataclasses import dataclass

from app.services.risk.stop_loss import PositionSnapshot


@dataclass(frozen=True)
class StopLossOverlay:
    active: bool
    market: str | None
    stop_loss_price: float | None
    label: str | None


class StopLossOverlayService:
    """Build chart overlay payloads for active stop-loss lines."""

    def build(self, position: PositionSnapshot | None) -> StopLossOverlay:
        if position is None:
            return StopLossOverlay(
                active=False,
                market=None,
                stop_loss_price=None,
                label=None,
            )

        return StopLossOverlay(
            active=True,
            market=position.market,
            stop_loss_price=position.stop_loss_price,
            label="STOP LOSS",
        )
