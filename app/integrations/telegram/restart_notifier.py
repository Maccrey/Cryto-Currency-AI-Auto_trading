from __future__ import annotations

import logging
from typing import Any

from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


class RestartMessageBuilder:
    """Build Telegram restart and recovery summary messages."""

    def build(
        self,
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
        market: str | None = None,
        trading_mode: str | None = None,
        learning_enabled: bool | None = None,
        dashboard_url: str | None = None,
        settings_url: str | None = None,
    ) -> str:
        portfolio = boot_state.portfolio_state
        cash_balance = portfolio.cash_balance if portfolio is not None else "unknown"
        asset_currency = portfolio.asset_currency if portfolio is not None else "unknown"
        asset_balance = portfolio.asset_balance if portfolio is not None else "unknown"
        status = "주의 필요" if boot_state.safe_mode or boot_state.hard_stop or not boot_state.trading_ready else "정상"
        mode_label = {"demo": "데모", "live": "실거래"}.get(trading_mode or "", trading_mode or "알 수 없음")

        lines = [
            "🚀 자동매매 서버 재시작 완료",
            "━━━━━━━━━━━━━━━━━━",
            f"앱: {app_name}  ·  시각: {restarted_at}",
            f"상태: {'✅ 정상' if status == '정상' else '⚠️ ' + status}  ·  사유: {cause}",
            f"시장: {market or '알 수 없음'}  ·  모드: {mode_label}",
            f"학습: {'켜짐' if learning_enabled else '꺼짐' if learning_enabled is not None else '알 수 없음'}",
            f"거래 준비: {'완료' if boot_state.trading_ready else '미완료'}  ·  안전 모드: {'켜짐' if boot_state.safe_mode else '꺼짐'}",
            f"HARD_STOP: {'발생' if boot_state.hard_stop else '없음'}  ·  실패 단계: {boot_state.failure_stage or '없음'}",
            f"자산: 현금 {cash_balance}원  ·  {asset_currency} {asset_balance}개",
            "ℹ️ 서버는 시작됐지만 자동매매 루프는 별도로 시작해야 합니다.",
        ]
        if dashboard_url is not None:
            lines.append(f"📊 대시보드: {dashboard_url}")
        if settings_url is not None:
            lines.append(f"⚙️ 설정: {settings_url}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


class RestartNotifier:
    """Send restart and recovery summaries through Telegram."""

    def __init__(
        self,
        *,
        gateway: Any,
        message_builder: RestartMessageBuilder | None = None,
    ) -> None:
        self._gateway = gateway
        self._message_builder = message_builder or RestartMessageBuilder()

    def notify_restarted(
        self,
        *,
        app_name: str,
        restarted_at: str,
        cause: str,
        boot_state: BootState,
        market: str | None = None,
        trading_mode: str | None = None,
        learning_enabled: bool | None = None,
        dashboard_url: str | None = None,
        settings_url: str | None = None,
    ) -> None:
        try:
            self._gateway.send_message(
                self._message_builder.build(
                    app_name=app_name,
                    restarted_at=restarted_at,
                    cause=cause,
                    boot_state=boot_state,
                    market=market,
                    trading_mode=trading_mode,
                    learning_enabled=learning_enabled,
                    dashboard_url=dashboard_url,
                    settings_url=settings_url,
                ),
            )
        except Exception:
            logger.exception(
                "telegram_restart_notification_failed",
                extra={
                    "app_name": app_name,
                    "market": market,
                    "trading_mode": trading_mode,
                    "cause": cause,
                },
            )
