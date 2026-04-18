from __future__ import annotations

from app.services.promotion.approval import PromotionApprovalFlow, PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation, PromotionEvaluator
from app.services.promotion.lifecycle import PromotionLifecycleService
from app.services.promotion.runner import (
    PromotionReviewRequest,
    PromotionRunResult,
    PromotionRunner,
)


class LifecycleNotificationDispatcherStub:
    def __init__(self) -> None:
        self.ready_calls: list[dict[str, object]] = []
        self.live_enabled_calls: list[dict[str, object]] = []

    def dispatch_promotion_ready(self, **kwargs) -> None:
        self.ready_calls.append(kwargs)

    def dispatch_live_enabled(self, **kwargs) -> None:
        self.live_enabled_calls.append(kwargs)


def build_runner(
    dispatcher: LifecycleNotificationDispatcherStub | None = None,
) -> PromotionRunner:
    lifecycle_service = PromotionLifecycleService(
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
    return PromotionRunner(lifecycle_service=lifecycle_service)


def test_promotion_runner_evaluates_and_enables_live_when_approved() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    runner = build_runner(dispatcher)

    result = runner.run(
        PromotionReviewRequest(
            market="KRW-XRP",
            demo_days=16,
            total_trades=132,
            profit_factor=1.31,
            max_drawdown=0.051,
            stoploss_failures=0,
            approval_granted=True,
            approved_by="manual_review",
            activated_at="2026-04-18T13:30:00+09:00",
        ),
    )

    assert result == PromotionRunResult(
        evaluation=PromotionEvaluation(
            status="READY_FOR_REVIEW",
            approved=False,
            rejection_reasons=[],
        ),
        approval_result=PromotionApprovalResult(
            live_enabled=True,
            safe_mode_entry=True,
            reason_code=None,
        ),
    )
    assert len(dispatcher.ready_calls) == 1
    assert len(dispatcher.live_enabled_calls) == 1


def test_promotion_runner_blocks_live_when_metrics_are_not_ready() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    runner = build_runner(dispatcher)

    result = runner.run(
        PromotionReviewRequest(
            market="KRW-XRP",
            demo_days=7,
            total_trades=64,
            profit_factor=1.08,
            max_drawdown=0.11,
            stoploss_failures=2,
            approval_granted=True,
            approved_by="manual_review",
            activated_at="2026-04-18T13:35:00+09:00",
        ),
    )

    assert result.evaluation.status == "NOT_READY"
    assert result.approval_result == PromotionApprovalResult(
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="PROMOTION_NOT_READY",
    )
    assert dispatcher.ready_calls == []
    assert dispatcher.live_enabled_calls == []


def test_promotion_runner_requires_manual_approval_after_ready_state() -> None:
    dispatcher = LifecycleNotificationDispatcherStub()
    runner = build_runner(dispatcher)

    result = runner.run(
        PromotionReviewRequest(
            market="KRW-XRP",
            demo_days=16,
            total_trades=132,
            profit_factor=1.31,
            max_drawdown=0.051,
            stoploss_failures=0,
            approval_granted=False,
            approved_by="manual_review",
            activated_at="2026-04-18T13:40:00+09:00",
        ),
    )

    assert result.evaluation.status == "READY_FOR_REVIEW"
    assert result.approval_result == PromotionApprovalResult(
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="MANUAL_APPROVAL_REQUIRED",
    )
    assert len(dispatcher.ready_calls) == 1
    assert dispatcher.live_enabled_calls == []
