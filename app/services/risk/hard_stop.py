from __future__ import annotations

from dataclasses import dataclass

from app.services.risk.stop_loss import PositionSnapshot


@dataclass(frozen=True)
class HardStopDecision:
    triggered: bool
    order_side: str
    quantity: float
    trigger_price: float
    reason_code: str | None
    is_stop_loss: bool


class HardStopMonitor:
    """Trigger a stop-loss exit when market price crosses the stored threshold."""

    def evaluate(
        self,
        *,
        position: PositionSnapshot,
        current_price: float,
    ) -> HardStopDecision:
        if current_price <= position.stop_loss_price:
            return HardStopDecision(
                triggered=True,
                order_side="sell",
                quantity=position.quantity,
                trigger_price=current_price,
                reason_code="STOP_LOSS_PRICE_HIT",
                is_stop_loss=True,
            )

        return HardStopDecision(
            triggered=False,
            order_side="sell",
            quantity=0.0,
            trigger_price=current_price,
            reason_code=None,
            is_stop_loss=False,
        )
