from __future__ import annotations

from app.integrations.telegram.hard_stop_notifier import HardStopNotifier
from app.services.recovery.orchestrator import BootState


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


def test_hard_stop_notifier_sends_restart_threshold_alert() -> None:
    gateway = StubTelegramGateway()
    notifier = HardStopNotifier(gateway=gateway)
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

    notifier.notify_hard_stop(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T12:15:00+09:00",
        boot_state=boot_state,
    )

    assert gateway.messages == [
        "[HARD_STOP_TRIGGERED]\n"
        "app=upbit-auto-trader\n"
        "market=KRW-XRP\n"
        "triggered_at=2026-04-18T12:15:00+09:00\n"
        "restart_count=3\n"
        "blocked_reason=RESTART_THRESHOLD_EXCEEDED\n"
        "safe_mode=True\n"
        "hard_stop=True\n"
        "trading_ready=False\n"
        "failure_stage=hard_stop"
    ]


def test_hard_stop_notifier_uses_unknown_when_reconcile_result_is_missing() -> None:
    gateway = StubTelegramGateway()
    notifier = HardStopNotifier(gateway=gateway)
    boot_state = BootState(
        safe_mode=True,
        hard_stop=True,
        trading_ready=False,
        failure_stage="hard_stop",
        portfolio_state=None,
        reconcile_result=None,
    )

    notifier.notify_hard_stop(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T12:20:00+09:00",
        boot_state=boot_state,
    )

    assert gateway.messages == [
        "[HARD_STOP_TRIGGERED]\n"
        "app=upbit-auto-trader\n"
        "market=KRW-XRP\n"
        "triggered_at=2026-04-18T12:20:00+09:00\n"
        "restart_count=unknown\n"
        "blocked_reason=unknown\n"
        "safe_mode=True\n"
        "hard_stop=True\n"
        "trading_ready=False\n"
        "failure_stage=hard_stop"
    ]
