from __future__ import annotations

import logging
from typing import Any

from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


class HardStopNotifier:
    """Send HARD_STOP operational alerts through Telegram."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_hard_stop(
        self,
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        boot_state: BootState,
    ) -> None:
        try:
            self._gateway.send_message(
                self._build_message(
                    app_name=app_name,
                    market=market,
                    triggered_at=triggered_at,
                    boot_state=boot_state,
                ),
            )
        except Exception:
            logger.exception(
                "telegram_hard_stop_notification_failed",
                extra={"app_name": app_name, "market": market},
            )

    @staticmethod
    def _build_message(
        *,
        app_name: str,
        market: str,
        triggered_at: str,
        boot_state: BootState,
    ) -> str:
        reconcile_result = boot_state.reconcile_result or {}
        restart_count = reconcile_result.get("restart_count", "unknown")
        blocked_reason = reconcile_result.get("blocked_reason", "unknown")

        return "\n".join([
            "🚨 자동매매 안전 정지",
            "━━━━━━━━━━━━━━━━━━",
            f"앱: {app_name}  ·  시장: {market}",
            f"발생 시각: {triggered_at}",
            f"차단 사유: {blocked_reason}",
            f"재시작 횟수: {restart_count}",
            f"안전 모드: {'켜짐' if boot_state.safe_mode else '꺼짐'}  ·  HARD_STOP: {'발생' if boot_state.hard_stop else '없음'}",
            f"거래 준비: {'완료' if boot_state.trading_ready else '미완료'}  ·  실패 단계: {boot_state.failure_stage or '없음'}",
            "⚠️ 원인을 확인하고 안전 상태를 복구하기 전까지 자동매매가 중지됩니다.",
            "━━━━━━━━━━━━━━━━━━",
        ])
