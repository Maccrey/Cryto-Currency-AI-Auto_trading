from __future__ import annotations

from app.integrations.telegram.promotion_notifier import PromotionNotifier


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


def test_promotion_notifier_sends_ready_message() -> None:
    gateway = StubTelegramGateway()
    notifier = PromotionNotifier(gateway=gateway)

    notifier.notify_ready(
        market="KRW-XRP",
        demo_days=14,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
    )

    assert gateway.messages == [
        "[PROMOTION_READY]\n"
        "market=KRW-XRP\n"
        "demo_days=14\n"
        "total_trades=132\n"
        "profit_factor=1.31\n"
        "max_drawdown=0.051"
    ]


def test_promotion_notifier_sends_live_enabled_message() -> None:
    gateway = StubTelegramGateway()
    notifier = PromotionNotifier(gateway=gateway)

    notifier.notify_live_enabled(
        market="KRW-XRP",
        approved_by="manual_review",
        activated_at="2026-04-18T12:00:00+09:00",
    )

    assert gateway.messages == [
        "[LIVE_MODE_ENABLED]\n"
        "market=KRW-XRP\n"
        "approved_by=manual_review\n"
        "activated_at=2026-04-18T12:00:00+09:00"
    ]

