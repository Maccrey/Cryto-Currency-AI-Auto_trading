from __future__ import annotations

from app.integrations.telegram.restart_notifier import RestartMessageBuilder, RestartNotifier
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


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
    )

    assert gateway.messages == [
        "[RESTARTED]\n"
        "app=upbit-auto-trader\n"
        "restarted_at=2026-04-18T11:00:00+09:00\n"
        "cause=process_restart\n"
        "safe_mode=True\n"
        "trading_ready=False\n"
        "failure_stage=open_order_reconcile\n"
        "cash_balance=250000.0\n"
        "asset_currency=XRP\n"
        "asset_balance=180.5"
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
        "[RESTARTED]\n"
        "app=upbit-auto-trader\n"
        "restarted_at=2026-04-18T11:05:00+09:00\n"
        "cause=fatal_exception\n"
        "safe_mode=True\n"
        "trading_ready=False\n"
        "failure_stage=portfolio_sync\n"
        "cash_balance=unknown\n"
        "asset_currency=unknown\n"
        "asset_balance=unknown"
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

    assert gateway.messages[0].startswith("[RESTARTED]\n")
    assert "trading_ready=True" in gateway.messages[0]
