from __future__ import annotations

from typing import Any


class PromotionNotifier:
    """Send promotion-related lifecycle messages through Telegram."""

    def __init__(self, *, gateway: Any) -> None:
        self._gateway = gateway

    def notify_ready(
        self,
        *,
        market: str,
        demo_days: int,
        total_trades: int,
        profit_factor: float,
        max_drawdown: float,
    ) -> None:
        self._gateway.send_message(
            "\n".join([
                "✅ 데모 성과 검토 준비 완료",
                "━━━━━━━━━━━━━━━━━━",
                f"시장: {market}  ·  데모 운용: {demo_days}일",
                f"완료 거래: {total_trades}회",
                f"수익 팩터: {profit_factor:.2f}  ·  최대 낙폭: {max_drawdown:.2%}",
                "실거래 전환은 설정과 승인 절차를 확인한 뒤 진행하세요.",
                "━━━━━━━━━━━━━━━━━━",
            ])
        )

    def notify_live_enabled(
        self,
        *,
        market: str,
        approved_by: str,
        activated_at: str,
    ) -> None:
        self._gateway.send_message(
            "\n".join([
                "🔴 실거래 모드 활성화",
                "━━━━━━━━━━━━━━━━━━",
                f"시장: {market}",
                f"승인자: {approved_by}",
                f"활성 시각: {activated_at}",
                "실제 주문이 제출될 수 있으니 거래소와 API 권한을 확인하세요.",
                "━━━━━━━━━━━━━━━━━━",
            ])
        )
