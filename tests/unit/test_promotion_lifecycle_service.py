from __future__ import annotations

from app.services.promotion.approval import PromotionApprovalFlow, PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation, PromotionEvaluator
from app.services.promotion.lifecycle import PromotionLifecycleService


class LifecycleNotificationDispatcherStub:
    def __init__(self) -> None:
        self.ready_calls: list[dict[str, object]] = []
        self.live_enabled_calls: list[dict[str, object]] = []

    def dispatch_promotion_ready(self, **kwargs) -> None:
        self.ready_calls.append(kwargs)

    def dispatch_live_enabled(self, **kwargs) -> None:
        self.live_enabled_calls.append(kwargs)


def build_service(
    dispatcher: LifecycleNotificationDispatcherStub | None = None,
) -> PromotionLifecycleService:
    return PromotionLifecycleService(
        evaluator=PromotionEvaluator(
            min_demo_days=14,
            min_trades=100,
            min_profit_factor=1.2,
            max_drawdown=0.08,
            max_stoploss_failures=0,
        ),
        approval_flow=PromotionApprovalFlow(),
        notification_dispatcher=dispatcher,
    )


def test_promotion_lifecycle_service_notifies_when_ready_for_review() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    service = build_service(dispatcher)

    evaluation = service.evaluate_readiness(
        market="KRW-XRP",
        demo_days=16,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
        stoploss_failures=0,
    )

    assert evaluation == PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )
    assert dispatcher.ready_calls == [
        {
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
        }
    ]


def test_promotion_lifecycle_service_skips_ready_notification_when_not_ready() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    service = build_service(dispatcher)

    evaluation = service.evaluate_readiness(
        market="KRW-XRP",
        demo_days=7,
        total_trades=64,
        profit_factor=1.08,
        max_drawdown=0.11,
        stoploss_failures=2,
    )

    assert evaluation.status == "NOT_READY"
    assert dispatcher.ready_calls == []


def test_promotion_lifecycle_service_notifies_when_live_is_enabled() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    service = build_service(dispatcher)
    evaluation = PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )

    result = service.enable_live(
        market="KRW-XRP",
        evaluation=evaluation,
        approval_granted=True,
        approved_by="manual_review",
        activated_at="2026-04-18T13:20:00+09:00",
    )

    assert result == PromotionApprovalResult(
        live_enabled=True,
        safe_mode_entry=True,
        reason_code=None,
    )
    assert dispatcher.live_enabled_calls == [
        {
            "market": "KRW-XRP",
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:20:00+09:00",
        }
    ]


def test_promotion_lifecycle_service_skips_live_notification_when_enable_fails() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    service = build_service(dispatcher)
    evaluation = PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )

    result = service.enable_live(
        market="KRW-XRP",
        evaluation=evaluation,
        approval_granted=False,
        approved_by="manual_review",
        activated_at="2026-04-18T13:20:00+09:00",
    )

    assert result == PromotionApprovalResult(
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="MANUAL_APPROVAL_REQUIRED",
    )
    assert dispatcher.live_enabled_calls == []
