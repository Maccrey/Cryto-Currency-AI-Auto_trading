from __future__ import annotations

from typing import Any

from app.services.execution.demo import FillResult


class TelegramNotifier:
    """Format and send trading notifications through a gateway."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_fill(self, fill: FillResult) -> None:
        self._gateway.send_message(self._build_fill_message(fill))

    @staticmethod
    def _build_fill_message(fill: FillResult) -> str:
        if fill.is_stop_loss:
            event_name = "STOP_LOSS_EXECUTED"
        elif fill.side == "buy":
            event_name = "BUY_EXECUTED"
        else:
            event_name = "SELL_EXECUTED"

        return (
            f"[{event_name}]\n"
            f"market={fill.market}\n"
            f"price={fill.filled_price}\n"
            f"quantity={fill.filled_quantity}\n"
            f"fee={fill.fee}\n"
            f"mode={fill.mode}"
        )
