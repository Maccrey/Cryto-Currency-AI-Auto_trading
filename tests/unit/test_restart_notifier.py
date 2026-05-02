from __future__ import annotations

from app.integrations.telegram.restart_notifier import RestartMessageBuilder, RestartNotifier
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


class FailingTelegramGateway:
    def send_message(self, message: str) -> None:
        raise RuntimeError("telegram unavailable")


def test_restart_notifier_sends_restart_summary_after_recovery() -> None:
    gateway = StubTelegramGateway()
    notifier = RestartNotifier(gateway=gateway)
    boot_state = BootState(
        safe_mode=True,
        hard_stop=False,
        trading_ready=False,
        failure_stage="open_order_reconcile",
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=180.5,
            avg_buy_price=815.0,
        ),
        reconcile_result=None,
    )

    notifier.notify_restarted(
        app_name="upbit-auto-trader",
        restarted_at="2026-04-18T11:00:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
        market="KRW-XRP",
        trading_mode="live",
        learning_enabled=True,
    )

    assert gateway.messages == [
        "자동매매 앱 서버가 시작되었습니다.\n"
        "앱 이름은 upbit-auto-trader이고 시작 시각은 2026-04-18T11:00:00+09:00입니다.\n"
        "현재 상태는 주의 필요이며 시작 사유는 process_restart입니다.\n"
        "거래 시장은 KRW-XRP이고 거래 모드는 live입니다.\n"
        "학습 기능은 켜짐입니다.\n"
        "자동 트레이딩은 아직 시작되지 않았습니다. 설정 화면에서 필수값을 저장한 뒤 서버 시작 버튼을 눌러야 시작됩니다.\n"
        "트레이딩 준비 상태는 중지이고 안전 모드는 켜짐입니다.\n"
        "HARD_STOP은 없음이며 실패 단계는 open_order_reconcile입니다.\n"
        "현금 잔고는 250000.0원, XRP 보유 수량은 180.5개입니다."
    ]


def test_restart_notifier_uses_unknown_for_missing_portfolio_snapshot() -> None:
    gateway = StubTelegramGateway()
    notifier = RestartNotifier(gateway=gateway)
    boot_state = BootState(
        safe_mode=True,
        hard_stop=False,
        trading_ready=False,
        failure_stage="portfolio_sync",
        portfolio_state=None,
        reconcile_result=None,
    )

    notifier.notify_restarted(
        app_name="upbit-auto-trader",
        restarted_at="2026-04-18T11:05:00+09:00",
        cause="fatal_exception",
        boot_state=boot_state,
    )

    assert gateway.messages == [
        "자동매매 앱 서버가 시작되었습니다.\n"
        "앱 이름은 upbit-auto-trader이고 시작 시각은 2026-04-18T11:05:00+09:00입니다.\n"
        "현재 상태는 주의 필요이며 시작 사유는 fatal_exception입니다.\n"
        "거래 시장은 알 수 없음이고 거래 모드는 알 수 없음입니다.\n"
        "학습 기능은 알 수 없음입니다.\n"
        "자동 트레이딩은 아직 시작되지 않았습니다. 설정 화면에서 필수값을 저장한 뒤 서버 시작 버튼을 눌러야 시작됩니다.\n"
        "트레이딩 준비 상태는 중지이고 안전 모드는 켜짐입니다.\n"
        "HARD_STOP은 없음이며 실패 단계는 portfolio_sync입니다.\n"
        "현금 잔고는 unknown원, unknown 보유 수량은 unknown개입니다."
    ]


def test_restart_notifier_accepts_message_builder() -> None:
    gateway = StubTelegramGateway()
    notifier = RestartNotifier(
        gateway=gateway,
        message_builder=RestartMessageBuilder(),
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=None,
        reconcile_result=None,
    )

    notifier.notify_restarted(
        app_name="upbit-auto-trader",
        restarted_at="2026-04-18T11:10:00+09:00",
        cause="deploy",
        boot_state=boot_state,
    )

    assert gateway.messages[0].startswith("자동매매 앱 서버가 시작되었습니다.\n")
    assert "자동 트레이딩은 아직 시작되지 않았습니다." in gateway.messages[0]
    assert "트레이딩 준비 상태는 정상" in gateway.messages[0]
    assert "현재 상태는 정상" in gateway.messages[0]


def test_restart_notifier_does_not_block_startup_when_gateway_fails() -> None:
    notifier = RestartNotifier(gateway=FailingTelegramGateway())
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=None,
        reconcile_result=None,
    )

    notifier.notify_restarted(
        app_name="upbit-auto-trader",
        restarted_at="2026-04-18T11:15:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
        market="KRW-XRP",
        trading_mode="demo",
        learning_enabled=True,
    )
