from __future__ import annotations

from app.integrations.telegram.boot_notification_dispatcher import BootNotificationDispatcher
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState


class RestartNotifierStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify_restarted(self, **kwargs) -> None:
        self.calls.append(kwargs)


class HardStopNotifierStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify_hard_stop(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_boot_notification_dispatcher_sends_restart_notification_for_normal_boot() -> None:
    restart_notifier = RestartNotifierStub()
    hard_stop_notifier = HardStopNotifierStub()
    dispatcher = BootNotificationDispatcher(
        restart_notifier=restart_notifier,
        hard_stop_notifier=hard_stop_notifier,
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=180.5,
            avg_buy_price=815.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    dispatcher.dispatch_boot_event(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T12:40:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert len(restart_notifier.calls) == 1
    assert restart_notifier.calls[0]["app_name"] == "upbit-auto-trader"
    assert restart_notifier.calls[0]["restarted_at"] == "2026-04-18T12:40:00+09:00"
    assert restart_notifier.calls[0]["cause"] == "process_restart"
    assert restart_notifier.calls[0]["market"] == "KRW-XRP"
    assert restart_notifier.calls[0]["trading_mode"] == "demo"
    assert restart_notifier.calls[0]["learning_enabled"] is True
    assert restart_notifier.calls[0]["boot_state"] == boot_state
    assert hard_stop_notifier.calls == []


def test_boot_notification_dispatcher_sends_hard_stop_notification_when_blocked() -> None:
    restart_notifier = RestartNotifierStub()
    hard_stop_notifier = HardStopNotifierStub()
    dispatcher = BootNotificationDispatcher(
        restart_notifier=restart_notifier,
        hard_stop_notifier=hard_stop_notifier,
    )
    boot_state = BootState(
        safe_mode=True,
        hard_stop=True,
        trading_ready=False,
        failure_stage="hard_stop",
        portfolio_state=None,
        reconcile_result={
            "restart_count": 3,
            "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
        },
    )

    dispatcher.dispatch_boot_event(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T12:45:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
    )

    assert restart_notifier.calls == []
    assert len(hard_stop_notifier.calls) == 1
    assert hard_stop_notifier.calls[0]["app_name"] == "upbit-auto-trader"
    assert hard_stop_notifier.calls[0]["market"] == "KRW-XRP"
    assert hard_stop_notifier.calls[0]["triggered_at"] == "2026-04-18T12:45:00+09:00"
    assert hard_stop_notifier.calls[0]["boot_state"] == boot_state


def test_boot_notification_dispatcher_is_noop_without_matching_notifier() -> None:
    dispatcher = BootNotificationDispatcher()
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=None,
        reconcile_result=None,
    )

    dispatcher.dispatch_boot_event(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T12:50:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
    )
