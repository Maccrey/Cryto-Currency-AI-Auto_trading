from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.services.execution.demo import FillResult

logger = logging.getLogger(__name__)


class FillMessageTemplate:
    """Build Telegram messages for execution fills."""

    def build(
        self,
        fill: FillResult,
        *,
        reason_code: str | None = None,
        entry_price: float | None = None,
        total_asset_value: float | None = None,
    ) -> str:
        if fill.is_stop_loss:
            title = "손절 매도가 체결되었습니다."
        elif fill.side == "buy":
            title = "매수가 체결되었습니다."
        else:
            title = "매도가 체결되었습니다."

        notional = _round_krw(fill.filled_price * fill.filled_quantity)
        lines = [
            title,
            f"{fill.market}에서 {fill.filled_price:,.2f}원에 {fill.filled_quantity:,.8f}개가 체결되었습니다.",
            f"체결 금액은 약 {notional:,.0f}원이고 수수료는 {fill.fee:,.2f}원입니다.",
            f"거래 모드는 {'데모' if fill.mode == 'demo' else '실거래'}입니다.",
        ]
        if total_asset_value is not None:
            lines.append(f"총 보유자산은 {total_asset_value:,.2f}원입니다.")
        if fill.side == "sell" and entry_price is not None:
            gross_profit = (fill.filled_price - entry_price) * fill.filled_quantity
            net_profit = gross_profit - fill.fee
            profit_rate = 0.0 if entry_price <= 0 else ((fill.filled_price - entry_price) / entry_price) * 100
            lines.append(
                f"평균 매수가 {entry_price:,.2f}원 기준으로 이번 매도 손익은 {net_profit:,.2f}원이고 수익률은 {profit_rate:,.2f}%입니다.",
            )
        if fill.is_stop_loss and reason_code is not None:
            lines.append(f"손절 사유는 {reason_code}입니다.")
        return "\n".join(lines)


def _round_krw(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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

    def notify_fill(
        self,
        fill: FillResult,
        *,
        reason_code: str | None = None,
        entry_price: float | None = None,
        total_asset_value: float | None = None,
    ) -> None:
        try:
            self._gateway.send_message(
                self._fill_message_template.build(
                    fill,
                    reason_code=reason_code,
                    entry_price=entry_price,
                    total_asset_value=total_asset_value,
                ),
            )
        except Exception:
            logger.exception(
                "telegram_fill_notification_failed",
                extra={
                    "market": fill.market,
                    "side": fill.side,
                    "mode": fill.mode,
                    "is_stop_loss": fill.is_stop_loss,
                },
            )
