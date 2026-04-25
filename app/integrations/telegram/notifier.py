from __future__ import annotations

from typing import Any

from app.services.execution.demo import FillResult


class FillMessageTemplate:
    """Build Telegram messages for execution fills."""

    def build(self, fill: FillResult, *, reason_code: str | None = None) -> str:
        if fill.is_stop_loss:
            event_name = "STOP_LOSS_EXECUTED"
        elif fill.side == "buy":
            event_name = "BUY_EXECUTED"
        else:
            event_name = "SELL_EXECUTED"

        message = (
            f"[{event_name}]\n"
            f"market={fill.market}\n"
            f"price={fill.filled_price}\n"
            f"quantity={fill.filled_quantity}\n"
            f"fee={fill.fee}\n"
            f"mode={fill.mode}"
        )
        if fill.is_stop_loss and reason_code is not None:
            message = f"{message}\nreason={reason_code}"
        return message


class TelegramNotifier:
    """Send trading notifications through a gateway."""

    def __init__(
        self,
        *,
        gateway: Any,
        fill_message_template: FillMessageTemplate | None = None,
    ) -> None:
        self._gateway = gateway
        self._fill_message_template = fill_message_template or FillMessageTemplate()

    def notify_fill(self, fill: FillResult, *, reason_code: str | None = None) -> None:
        self._gateway.send_message(
            self._fill_message_template.build(fill, reason_code=reason_code),
        )
