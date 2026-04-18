from __future__ import annotations

from app.integrations.telegram.lifecycle_notification_dispatcher import (
    LifecycleNotificationDispatcher,
)
from app.services.recovery.orchestrator import BootState


class BootDispatcherStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def dispatch_boot_event(self, **kwargs) -> None:
        self.calls.append(kwargs)


class PromotionNotifierStub:
    def __init__(self) -> None:
        self.ready_calls: list[dict[str, object]] = []
        self.live_enabled_calls: list[dict[str, object]] = []

    def notify_ready(self, **kwargs) -> None:
        self.ready_calls.append(kwargs)

    def notify_live_enabled(self, **kwargs) -> None:
        self.live_enabled_calls.append(kwargs)


def test_lifecycle_dispatcher_routes_boot_events_to_boot_dispatcher() -> None:
    boot_dispatcher = BootDispatcherStub()
    dispatcher = LifecycleNotificationDispatcher(boot_dispatcher=boot_dispatcher)
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
        triggered_at="2026-04-18T13:00:00+09:00",
        cause="process_restart",
        boot_state=boot_state,
    )

    assert boot_dispatcher.calls == [
        {
            "app_name": "upbit-auto-trader",
            "market": "KRW-XRP",
            "triggered_at": "2026-04-18T13:00:00+09:00",
            "cause": "process_restart",
            "boot_state": boot_state,
        }
    ]


def test_lifecycle_dispatcher_routes_promotion_ready_events() -> None:
    promotion_notifier = PromotionNotifierStub()
    dispatcher = LifecycleNotificationDispatcher(
        promotion_notifier=promotion_notifier,
    )

    dispatcher.dispatch_promotion_ready(
        market="KRW-XRP",
        demo_days=14,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
    )

    assert promotion_notifier.ready_calls == [
        {
            "market": "KRW-XRP",
            "demo_days": 14,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
        }
    ]


def test_lifecycle_dispatcher_routes_live_enabled_events() -> None:
    promotion_notifier = PromotionNotifierStub()
    dispatcher = LifecycleNotificationDispatcher(
        promotion_notifier=promotion_notifier,
    )

    dispatcher.dispatch_live_enabled(
        market="KRW-XRP",
        approved_by="manual_review",
        activated_at="2026-04-18T13:05:00+09:00",
    )

    assert promotion_notifier.live_enabled_calls == [
        {
            "market": "KRW-XRP",
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:05:00+09:00",
        }
    ]


def test_lifecycle_dispatcher_is_noop_without_matching_notifier() -> None:
    dispatcher = LifecycleNotificationDispatcher()

    dispatcher.dispatch_promotion_ready(
        market="KRW-XRP",
        demo_days=14,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
    )
    dispatcher.dispatch_live_enabled(
        market="KRW-XRP",
        approved_by="manual_review",
        activated_at="2026-04-18T13:05:00+09:00",
    )
    dispatcher.dispatch_boot_event(
        app_name="upbit-auto-trader",
        market="KRW-XRP",
        triggered_at="2026-04-18T13:00:00+09:00",
        cause="process_restart",
        boot_state=BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=None,
            reconcile_result=None,
        ),
    )
