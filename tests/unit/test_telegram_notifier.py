from __future__ import annotations

from app.integrations.telegram.notifier import FillMessageTemplate, TelegramNotifier
from app.services.execution.demo import FillResult


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


class FailingTelegramGateway:
    def send_message(self, message: str) -> None:
        raise RuntimeError("telegram unavailable")


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
        reason_code="STOP_LOSS_EXPECTATION_FAILED",
    )

    assert gateway.messages == [
        "[STOP_LOSS_EXECUTED]\n"
        "market=KRW-XRP\n"
        "price=805.0\n"
        "quantity=190.5\n"
        "fee=63.84\n"
        "mode=live\n"
        "reason=STOP_LOSS_EXPECTATION_FAILED"
    ]


def test_telegram_notifier_accepts_fill_message_template() -> None:
    gateway = StubTelegramGateway()
    notifier = TelegramNotifier(
        gateway=gateway,
        fill_message_template=FillMessageTemplate(),
    )

    notifier.notify_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=830.0,
            filled_quantity=50.0,
            fee=17.27,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )

    assert gateway.messages == [
        "[SELL_EXECUTED]\n"
        "market=KRW-XRP\n"
        "price=830.0\n"
        "quantity=50.0\n"
        "fee=17.27\n"
        "mode=demo"
    ]


def test_telegram_notifier_does_not_block_trading_when_gateway_fails() -> None:
    notifier = TelegramNotifier(gateway=FailingTelegramGateway())

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
