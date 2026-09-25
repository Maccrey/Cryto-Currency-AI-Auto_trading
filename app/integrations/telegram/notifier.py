from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from app.services.execution.demo import FillResult
from app.services.reporting.daily_goal import progress_bar

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
        daily_goal_progress: dict[str, Any] | None = None,
    ) -> str:
        if fill.is_stop_loss:
            title = "🛑 손절 매도 체결"
        elif fill.side == "buy":
            title = "🟢 매수 체결"
        else:
            title = "🔵 매도 체결"

        notional = _round_krw(fill.filled_price * fill.filled_quantity)
        lines = [
            "━━━━━━━━━━━━━━━━━━",
            title,
            f"📍 {fill.market}  ·  {'데모' if fill.mode == 'demo' else '실거래'}",
            f"체결가  {fill.filled_price:,.2f}원",
            f"수량    {fill.filled_quantity:,.8f}",
            f"거래금액 약 {notional:,.0f}원  ·  수수료 {fill.fee:,.2f}원",
        ]
        if total_asset_value is not None:
            lines.append(f"💼 체결 후 총 자산 약 {total_asset_value:,.0f}원")
        if market_state_label:
            if market_state_label == "박스권" and box_range_low is not None and box_range_high is not None:
                lines.append(f"📊 장세 박스권  ·  {box_range_low:,.2f}~{box_range_high:,.2f}원")
            else:
                lines.append(f"📊 장세 {market_state_label}")
        if fill.side == "sell" and entry_price is not None:
            gross_profit = (fill.filled_price - entry_price) * fill.filled_quantity
            net_profit = gross_profit - fill.fee
            profit_rate = 0.0 if entry_price <= 0 else ((fill.filled_price - entry_price) / entry_price) * 100
            pnl_icon = "📈" if net_profit >= 0 else "📉"
            lines.extend([
                "",
                f"{pnl_icon} 이번 매도 손익 {net_profit:+,.2f}원 · 가격 기준 {profit_rate:+,.3f}%",
                f"평균 매수가 {entry_price:,.2f}원 기준 · 매도 수수료 차감",
            ])
            if daily_goal_progress and daily_goal_progress.get("available"):
                goal_pct = float(daily_goal_progress.get("target_return_rate", 0.001)) * 100
                realized_pct = float(daily_goal_progress.get("return_rate", 0.0)) * 100
                progress_pct = float(daily_goal_progress.get("progress_pct", 0.0))
                progress_text = f"{progress_pct:.1f}%" if progress_pct >= 0 else f"−{abs(progress_pct):.1f}%"
                lines.extend([
                    "",
                    f"🎯 24시간 목표 +{goal_pct:.2f}%  ·  달성 {progress_text}",
                    f"{progress_bar(progress_pct)}  실현 {realized_pct:+.3f}% / {float(daily_goal_progress.get('initial_capital', 0)):,.0f}원 기준",
                ])
        if fill.is_stop_loss and reason_code is not None:
            lines.append(f"손절 사유: {_reason_label(reason_code)}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


def _round_krw(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _reason_label(reason_code: str) -> str:
    labels = {
        "TAKE_PROFIT_TARGET_HIT": "익절 목표 도달",
        "TRAILING_STOP_HIT": "트레일링 스톱 도달",
        "STOP_LOSS_HIT": "손절 기준 도달",
        "MARKET_STATE_BEAR": "하락 장세 위험 대응",
        "POST_SELL_REENTRY_EDGE_REQUIRED": "매도 후 재진입 조건 미충족",
    }
    return labels.get(reason_code, reason_code.replace("_", " ").strip().capitalize())


class TelegramNotifier:
    """Send trading notifications through a gateway."""

    def __init__(
        self,
        *,
        gateway: Any,
        fill_message_template: FillMessageTemplate | None = None,
        server_name_provider: Callable[[], str] | None = None,
        daily_goal_progress_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._gateway = gateway
        self._fill_message_template = fill_message_template or FillMessageTemplate()
        self._server_name_provider = server_name_provider
        self._daily_goal_progress_provider = daily_goal_progress_provider

    def set_daily_goal_progress_provider(self, provider: Callable[[], dict[str, Any]]) -> None:
        self._daily_goal_progress_provider = provider

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
            daily_goal_progress = None
            if self._daily_goal_progress_provider is not None:
                try:
                    daily_goal_progress = self._daily_goal_progress_provider()
                except Exception:
                    logger.exception("telegram_daily_goal_progress_failed")
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
                        daily_goal_progress=daily_goal_progress,
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
                "⚠️ 시장 변동성 알림",
                "━━━━━━━━━━━━━━━━━━",
                f"{label} 감지  ·  {market}",
                f"현재가 {current_price:,.2f}원  ·  최근 변화 {recent_change_pct * 100:+.2f}%",
                f"모드: {'데모' if mode == 'demo' else '실거래'}",
                f"대응: {action}",
                "━━━━━━━━━━━━━━━━━━",
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
                "🔄 매매 룰 변경",
                "━━━━━━━━━━━━━━━━━━",
                f"시장 {market}  ·  {'데모' if mode == 'demo' else '실거래'}",
                f"이전  {previous_label} ({previous_rate_text})",
                f"적용  {applied_variant_label} ({applied_profit_rate * 100:+.2f}%)",
                f"전환  {selection_label}",
                f"근거  {reason}",
                "━━━━━━━━━━━━━━━━━━",
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

    def notify_etf_context_changed(
        self,
        *,
        market: str,
        mode: str,
        previous: dict[str, object],
        current: dict[str, object],
        changed_fields: list[str],
    ) -> None:
        message = "\n".join(
            [
                "🧾 XRP ETF 데이터 변경",
                "━━━━━━━━━━━━━━━━━━",
                f"시장 {market}  ·  {'데모' if mode == 'demo' else '실거래'}",
                f"변경 항목: {', '.join(changed_fields)}",
                f"상태: {previous.get('state') or '-'} → {current.get('state') or '-'}",
                f"순흐름: {float(previous.get('flow_usd') or 0):,.0f} → {float(current.get('flow_usd') or 0):,.0f} USD",
                f"AUM: {float(previous.get('total_aum_usd') or 0):,.0f} → {float(current.get('total_aum_usd') or 0):,.0f} USD",
                f"보유량: {float(previous.get('total_holding_coin') or 0):,.0f} → {float(current.get('total_holding_coin') or 0):,.0f} XRP",
                f"기준일 {current.get('flow_date') or '-'}  ·  데이터 {current.get('data_status') or '-'}",
                "━━━━━━━━━━━━━━━━━━",
            ],
        )
        try:
            self._gateway.send_message(self._format_message(message))
        except Exception:
            logger.exception("telegram_etf_context_change_notification_failed", extra={"market": market, "mode": mode})

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
