from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

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
        market_state_label: str | None = None,
        box_range_low: float | None = None,
        box_range_high: float | None = None,
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
        if market_state_label:
            if market_state_label == "박스권" and box_range_low is not None and box_range_high is not None:
                lines.append(f"현재 장세는 박스권이며 레인지는 {box_range_low:,.2f}원부터 {box_range_high:,.2f}원입니다.")
            else:
                lines.append(f"현재 장세는 {market_state_label}입니다.")
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
        server_name_provider: Callable[[], str] | None = None,
    ) -> None:
        self._gateway = gateway
        self._fill_message_template = fill_message_template or FillMessageTemplate()
        self._server_name_provider = server_name_provider

    def notify_fill(
        self,
        fill: FillResult,
        *,
        reason_code: str | None = None,
        entry_price: float | None = None,
        total_asset_value: float | None = None,
        market_state_label: str | None = None,
        box_range_low: float | None = None,
        box_range_high: float | None = None,
    ) -> None:
        try:
            self._gateway.send_message(
                self._format_message(
                    self._fill_message_template.build(
                        fill,
                        reason_code=reason_code,
                        entry_price=entry_price,
                        total_asset_value=total_asset_value,
                        market_state_label=market_state_label,
                        box_range_low=box_range_low,
                        box_range_high=box_range_high,
                    ),
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

    def notify_market_shock(
        self,
        *,
        market: str,
        shock_type: str,
        recent_change_pct: float,
        current_price: float,
        mode: str,
    ) -> None:
        label = "급락" if shock_type == "crash" else "급등"
        action = (
            "급락이 진정되고 상승세가 확인될 때까지 신규 매수는 관망합니다."
            if shock_type == "crash"
            else "급등 변동성이 감지되어 추격 매수 리스크를 점검합니다."
        )
        message = "\n".join(
            [
                f"{label} 변동성이 감지되었습니다.",
                f"{market} 현재가는 {current_price:,.2f}원이고 최근 변화율은 {recent_change_pct * 100:,.2f}%입니다.",
                f"거래 모드는 {'데모' if mode == 'demo' else '실거래'}입니다.",
                action,
            ],
        )
        try:
            self._gateway.send_message(self._format_message(message))
        except Exception:
            logger.exception(
                "telegram_market_shock_notification_failed",
                extra={
                    "market": market,
                    "shock_type": shock_type,
                    "mode": mode,
                },
            )

    def notify_rule_variant_changed(
        self,
        *,
        market: str,
        mode: str,
        previous_variant_label: str | None,
        previous_profit_rate: float | None,
        applied_variant_label: str,
        applied_profit_rate: float,
        selection_type: str | None,
        reason: str,
    ) -> None:
        selection_label = (
            "적용 룰 손절 후 즉시 전환"
            if selection_type == "stop_loss_forced_switch"
            else "성과 검증 통과 후 자동 승격"
        )
        previous_label = previous_variant_label or "기존 적용 룰 없음"
        previous_rate_text = (
            "수익률 집계 없음"
            if previous_profit_rate is None
            else f"누적 수익률 {previous_profit_rate * 100:,.2f}%"
        )
        message = "\n".join(
            [
                "매매 룰이 변경되었습니다.",
                f"시장: {market} / 모드: {'데모' if mode == 'demo' else '실거래'}",
                f"변경 전: {previous_label} ({previous_rate_text})",
                f"변경 후: {applied_variant_label} (누적 수익률 {applied_profit_rate * 100:,.2f}%)",
                f"전환 유형: {selection_label}",
                f"변경 근거: {reason}",
            ],
        )
        try:
            self._gateway.send_message(self._format_message(message))
        except Exception:
            logger.exception(
                "telegram_rule_variant_change_notification_failed",
                extra={
                    "market": market,
                    "mode": mode,
                    "selection_type": selection_type,
                },
            )

    def _format_message(self, message: str) -> str:
        server_name = self._current_server_name()
        if not server_name:
            return message
        if message.startswith(f"[{server_name}]\n"):
            return message
        return f"[{server_name}]\n{message}"

    def _current_server_name(self) -> str:
        if self._server_name_provider is None:
            return ""
        try:
            return self._server_name_provider().strip()
        except Exception:
            return ""
