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
        "매수가 체결되었습니다.\n"
        "KRW-XRP에서 820.00원에 120.50000000개가 체결되었습니다.\n"
        "체결 금액은 약 98,810원이고 수수료는 41.11원입니다.\n"
        "거래 모드는 데모입니다."
    ]


def test_telegram_notifier_includes_total_asset_value_when_provided() -> None:
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
        total_asset_value=999958.89,
    )

    assert "총 보유자산은 999,958.89원입니다." in gateway.messages[0]


def test_telegram_notifier_prefixes_fill_message_with_server_name() -> None:
    gateway = StubTelegramGateway()
    notifier = TelegramNotifier(
        gateway=gateway,
        server_name_provider=lambda: "서울-데모-1",
    )

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

    assert gateway.messages[0].startswith("[서울-데모-1]\n매수가 체결되었습니다.")


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
        "손절 매도가 체결되었습니다.\n"
        "KRW-XRP에서 805.00원에 190.50000000개가 체결되었습니다.\n"
        "체결 금액은 약 153,353원이고 수수료는 63.84원입니다.\n"
        "거래 모드는 실거래입니다.\n"
        "손절 사유는 STOP_LOSS_EXPECTATION_FAILED입니다."
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
        entry_price=800.0,
    )

    assert gateway.messages == [
        "매도가 체결되었습니다.\n"
        "KRW-XRP에서 830.00원에 50.00000000개가 체결되었습니다.\n"
        "체결 금액은 약 41,500원이고 수수료는 17.27원입니다.\n"
        "거래 모드는 데모입니다.\n"
        "평균 매수가 800.00원 기준으로 이번 매도 손익은 1,482.73원이고 수익률은 3.75%입니다."
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


def test_telegram_notifier_sends_market_shock_message_with_server_name() -> None:
    gateway = StubTelegramGateway()
    notifier = TelegramNotifier(
        gateway=gateway,
        server_name_provider=lambda: "서울-데모-1",
    )

    notifier.notify_market_shock(
        market="KRW-XRP",
        shock_type="crash",
        recent_change_pct=-0.018,
        current_price=785.0,
        mode="demo",
    )

    assert gateway.messages[0].startswith("[서울-데모-1]\n급락 변동성이 감지되었습니다.")
    assert "최근 변화율은 -1.80%" in gateway.messages[0]
    assert "신규 매수는 관망합니다." in gateway.messages[0]


def test_telegram_notifier_includes_market_state_and_box_range() -> None:
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
        market_state_label="박스권",
        box_range_low=800.0,
        box_range_high=840.0,
    )

    assert "현재 장세는 박스권이며 레인지는 800.00원부터 840.00원입니다." in gateway.messages[0]
