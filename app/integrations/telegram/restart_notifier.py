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

        lines = [
            "자동매매 앱 서버가 시작되었습니다.",
            f"앱 이름은 {app_name}이고 시작 시각은 {restarted_at}입니다.",
            f"현재 상태는 {status}이며 시작 사유는 {cause}입니다.",
            f"거래 시장은 {market or '알 수 없음'}이고 거래 모드는 {trading_mode or '알 수 없음'}입니다.",
            f"학습 기능은 {'켜짐' if learning_enabled else '꺼짐' if learning_enabled is not None else '알 수 없음'}입니다.",
            "자동 트레이딩은 아직 시작되지 않았습니다. 설정 화면에서 필수값을 저장한 뒤 서버 시작 버튼을 눌러야 시작됩니다.",
            f"트레이딩 준비 상태는 {'정상' if boot_state.trading_ready else '중지'}이고 안전 모드는 {'켜짐' if boot_state.safe_mode else '꺼짐'}입니다.",
            f"HARD_STOP은 {'발생' if boot_state.hard_stop else '없음'}이며 실패 단계는 {boot_state.failure_stage or '없음'}입니다.",
            f"현금 잔고는 {cash_balance}원, {asset_currency} 보유 수량은 {asset_balance}개입니다.",
        ]
        if dashboard_url is not None:
            lines.append(f"대시보드는 브라우저에서 {dashboard_url} 주소로 열 수 있습니다.")
        if settings_url is not None:
            lines.append(f"설정 화면은 브라우저에서 {settings_url} 주소로 열 수 있습니다.")
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
