from __future__ import annotations

from app.integrations.telegram.notifier import TelegramNotifier
from app.services.execution.demo import FillResult


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


def test_telegram_notifier_sends_buy_fill_message() -> None:
    gateway = StubTelegramGateway()
    notifier = TelegramNotifier(gateway=gateway)

    notifier.notify_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=120.5,
            fee=41.11,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )

    assert gateway.messages == [
        "[BUY_EXECUTED]\n"
        "market=KRW-XRP\n"
        "price=820.0\n"
        "quantity=120.5\n"
        "fee=41.11\n"
        "mode=demo"
    ]


def test_telegram_notifier_sends_stop_loss_fill_message() -> None:
    gateway = StubTelegramGateway()
    notifier = TelegramNotifier(gateway=gateway)

    notifier.notify_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=805.0,
            filled_quantity=190.5,
            fee=63.84,
            status="filled",
            mode="live",
            is_virtual=False,
            is_stop_loss=True,
        ),
    )

    assert gateway.messages == [
        "[STOP_LOSS_EXECUTED]\n"
        "market=KRW-XRP\n"
        "price=805.0\n"
        "quantity=190.5\n"
        "fee=63.84\n"
        "mode=live"
    ]

